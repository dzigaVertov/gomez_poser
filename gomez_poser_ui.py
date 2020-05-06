import bpy
from bpy.props import FloatProperty, IntProperty, BoolProperty, PointerProperty, CollectionProperty
import re
import bpy
from mathutils import Vector
import bmesh


# 2) Cambiar a la opción swing para las constraints de los huesos de deformación
# 3) Hacer que cada invocación ponga los huesos en un grupo diferente
# 4) Hacer que funcione con el objeto seleccionado y con el último stroke dibujado o con todos los strokes seleccionados.


D = bpy.data
C = bpy.context


class FittedHandle(bpy.types.PropertyGroup):
    """
    Grupo donde se guardan los datos de la curva fiteada. 
    """
    handle_l: bpy.props.FloatVectorProperty()
    ctrl_point: bpy.props.FloatVectorProperty()
    handle_r: bpy.props.FloatVectorProperty()
    h_coef: bpy.props.FloatProperty()


class GopoProperties(bpy.types.PropertyGroup):
    """
    Variables de configuración de Gomez Poser
    """
    error_threshold: bpy.props.FloatProperty(default=0.05)
    num_bones: IntProperty(name='gopo_num_bones', default=3, min=2)
    num_bendy: IntProperty(
        name='gopo_num_bendy', default=16, min=1, max=32)
    initialized: BoolProperty(name='initialized', default=False)
    ob_armature: PointerProperty(type=bpy.types.Object,
                                 poll=lambda self, object: object.type == 'ARMATURE')


bpy.utils.register_class(GopoProperties)
bpy.utils.register_class(FittedHandle)


def add_auxiliary_meshes():
    """
    Crear objetos para reemplazar la apariencia de ctrl bones
    """
    initialized = C.window_manager.gopo_prop_group.initialized
    if initialized:
        return
    
    # Crear collection para guardar meshes auxiliares
    aux_col = bpy.data.collections.new('auxiliary_meshes')
    C.scene.collection.children.link(aux_col)
    aux_col.hide_viewport = True
    aux_col.hide_render = True

    # ESFERA
    # Crear objeto y mesh vacíos
    control_sphere_mesh = bpy.data.meshes.new('ctrl_sphere')
    ctrl_sphere_ob = bpy.data.objects.new('ctrl_sphere', control_sphere_mesh)
    # Linkear objeto a collection, hacer activo
    aux_col.objects.link(ctrl_sphere_ob)
    ctrl_sphere_ob.select_set(True)
    C.view_layer.objects.active = ctrl_sphere_ob

    # Crear geometría
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=4, v_segments=3, diameter=0.25)
    bm.to_mesh(control_sphere_mesh)
    bm.free()

    ctrl_sphere_ob.display_type = 'WIRE'

    # CONO
    # Crear objeto y mesh vacíos
    control_cone_mesh = bpy.data.meshes.new('ctrl_cone')
    ctrl_cone_ob = bpy.data.objects.new('ctrl_cone', control_cone_mesh)
    # Linkear objeto a collection, hacer activo
    aux_col.objects.link(ctrl_cone_ob)
    ctrl_cone_ob.select_set(True)
    C.view_layer.objects.active = ctrl_cone_ob

    # Crear geometría
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=True, segments= 8, diameter1=0.25, depth=0.25)
    bm.to_mesh(control_cone_mesh)
    bm.free()

    ctrl_cone_ob.display_type = 'WIRE'

    initialized = True


def change_context(ob, obtype='GPENCIL'):
    """
    Modificar el contexto para cambiar los pesos
    de los vertex groups de grease pencil
    """
    for area in C.screen.areas:
        if area.type == "VIEW_3D":
            break
    for region in area.regions:
        if region.type == "WINDOW":
            break

    space = area.spaces[0]
    con = C.copy()
    con['area'] = area
    con['region'] = region
    con['space_data'] = space
    if obtype == 'GPENCIL':
        con['active_gpencil_frame'] = ob.data.layers.active.active_frame
        con['editable_gpencil_layers'] = ob.data.layers
    elif obtype == 'ARMATURE':
        con['active_object'] = ob

    return con


def find_closest(distance, bones_positions, accumulated):
    """
    De la lista de distancias accumulated, devuelve el 
    índice del elemento más cercano a distance.
    TO DO: Hacer que esto sea un poco menos absurdo.
    """
    closest = len(bones_positions)
    for i in range(len(bones_positions), len(accumulated)):
        if distance > accumulated[i]:
            closest = i
        else:
            if accumulated[i] - distance > distance - accumulated[closest]:
                return closest
            else:
                return i
    return closest


def get_stroke_length(stroke, start=0, end=None):
    """
    Calcula el largo total de un stroke entre dos puntos
    y las distancias parciales entre cada punto y el primero
    """
    if not end:
        end = len(stroke.points)

    points = stroke.points
    stroke_length = 0
    accumulated = [0]
    for i in range(start, end-1):
        stroke_length += (points[i].co - points[i+1].co).length
        accumulated.append(stroke_length)

    return stroke_length, accumulated


def get_points_indices(stroke):
    """
    Devuelve los índices de los puntos que corresponden
    a las posiciones de cada uno de los huesos. 
    """

    num_bones = bpy.context.window_manager.gopo_prop_group.num_bones
    stroke_length, accumulated = get_stroke_length(stroke)
    distance_btw_bones = stroke_length/num_bones

    points_indices = []
    for i in range(num_bones):
        distance = i*distance_btw_bones
        points_indices.append(find_closest(
            distance, points_indices, accumulated))
    points_indices.append(len(stroke.points)-1)

    return points_indices


def get_bones_positions(stroke):
    """
    Devuelve las posiciones de los 
    huesos a lo largo del stroke
    """
    h_coefs = C.window_manager.fitted_curve_coefs
    bones_positions = [(i.ctrl_point, j.ctrl_point) for i,j in zip(h_coefs[:-1],h_coefs[1:])]
    return bones_positions


def add_deform_bones(armature, pos):
    """
    Creates deform bones - Puts bones in positions
    Creates the hierarchy - Calculates roll
    Puts Deform bones in last layer    
    """
    armature.select_set(True)
    C.view_layer.objects.active = armature
    num_bones = C.window_manager.gopo_prop_group.num_bones
    num_bendy = C.window_manager.gopo_prop_group.num_bendy

    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    ed_bones = armature.data.edit_bones

    for i,pos in enumerate(pos):
        print('creating a boney bone')
        head, tail = pos
        name = 'boney_' + str(i)
        print('bone_name: ', name)
        ed_bones.new(name)

        ed_bones[name].head = head
        ed_bones[name].tail = tail
        ed_bones[name].bbone_segments = num_bendy
        ed_bones[name].use_deform = True
        ed_bones[name].roll = 0.0

        if i > 0:
            ed_bones[name].parent = ed_bones['boney_' + str(i-1)]
            ed_bones[name].use_connect = True
            ed_bones[name].inherit_scale = 'NONE'
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Y')

    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in armature.data.bones:
        if bone.name.startswith('boney'):
            bone.layers[-1] = True
            bone.layers[0] = False

def add_handles(armature, name, i):
    """
    Sets handle bones as bezier handles for the deform bone
    """
    bones = armature.data.bones
    def_bone = bones['boney_' + str(i)]
    def_bone.bbone_custom_handle_start = bones[name + '_left_' + str(i)]
    def_bone.bbone_handle_type_start = 'ABSOLUTE'
    def_bone.bbone_custom_handle_end = bones[name + '_right_' + str(i)]
    def_bone.bbone_handle_type_end = 'ABSOLUTE'

def add_copy_location(armature, name, i):
    """
    Adds a copy location contraint to the i-th bone
    targeting the "name" bone
    """
    pbones = armature.pose.bones

    constr = pbones['boney_' + str(i)].constraints.new(type='COPY_LOCATION')
    constr.target = armature
    constr.subtarget = name


def add_stretch_to(armature, name, i):
    """
    Adds a stretch-to contraint to the i-th bone
    targeting the "name" bone
    """
    pbones = armature.pose.bones

    constr = pbones['boney_' + str(i-1)].constraints.new(type='STRETCH_TO')
    constr.target = armature
    constr.subtarget = name
    constr.keep_axis = 'SWING_Y'


def add_control_bones(armature, pos):
    """
    Adds control bones in pos positions pointing up (for now) - 
    Adds handle_bones
    Sets to no-deform - Adds copy location and stretch-to constraints
    Adds custom shapes - Puts control bones in first layer.
    """
    h_coefs = C.window_manager.fitted_curve_coefs
    handles = [(i.handle_l, i.handle_r) for i in h_coefs ]
    
    armature.select_set(True)
    C.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    ed_bones = armature.data.edit_bones

    for i, p in enumerate(pos):
        name = 'ctrl_stroke_' + str(i)
        ctrl, _ = p
        ed_bones.new(name)
        ed_bones[name].head = Vector(ctrl)
        ed_bones[name].tail = Vector(ctrl) + Vector((0.0, 0.0, 1.0))
        ed_bones[name].use_deform = False

        
    for i, h in enumerate(handles):
        h_left, h_right = map(Vector, h)
        name_left = 'handle_left_' + str(i)
        name_right = 'handle_right_' + str(i)
        ed_bones.new(name_left)
        ed_bones.new(name_right)
        ed_bones[name_left].head = h_left
        ed_bones[name_right].head = h_right
        ed_bones[name_left].tail = h_left + Vector((0.0, 0.0, 1.0))
        ed_bones[name_left].use_deform = False
        ed_bones[name_right].tail = h_right + Vector((0.0, 0.0, 1.0))
        ed_bones[name_right].use_deform = False


    bpy.ops.object.mode_set(mode='OBJECT')
    for i, p in enumerate(pos):
        name = 'ctrl_stroke_' + str(i)
        # adding constraints
        if i < len(pos)-1:
            add_copy_location(armature, name, i)
        if i > 0:
            add_stretch_to(armature, name, i)

        # setting handles
        add_handles(armature, 'handle', i)
        
    pbones = armature.pose.bones
    for bone in pbones:
        if bone.name.startswith('ctrl'):
            bone.custom_shape = D.objects['ctrl_sphere']
            bone.custom_shape_scale = 0.5
            armature.data.bones[bone.name].show_wire = True
            armature.data.bones[bone.name].layers[0] = True
            armature.data.bones[bone.name].layers[-1] = False

        if bone.name.startswith('handle'):
            bone.custom_shape = D.objects['ctrl_cone']
            bone.custom_shape_scale = 0.25
            armature.data.bones[bone.name].show_wire = True
            armature.data.bones[bone.name].layers[0] = True
            armature.data.bones[bone.name].layers[-1] = False


def add_armature(gp_ob, stroke, armature):
    """
    Adds an armature modifier to the greasepencil object
    Adds a new vertex group containing the stroke
    Sets the modifier to affect only that vertex group
    """
    mod = gp_ob.grease_pencil_modifiers.new(type='GP_ARMATURE',
                                            name=armature.name)
    mod.object = armature

    C.view_layer.objects.active = gp_ob
    bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
    for pt in stroke.points:
        pt.select = True

    con = change_context(gp_ob)
    gp_ob.vertex_groups.new(name=armature.name)
    bpy.ops.gpencil.vertex_group_assign(con)
    mod.vertex_group = armature.name


def get_vg_number(name):
    """
    Extracts the number in a bone name
    """
    number = re.search('(\d*)$', name).group()
    if len(number):
        return int(number)
    else:
        return 'NOBONE'


def add_vertex_groups(gp_ob, armature):
    """
    Add a vertex group for every deform bone
    """
    for b in armature.data.bones:
        if b.use_deform:
            gp_ob.vertex_groups.new(name=b.name)


def add_weights(gp_ob, stroke):
    """
    Asigna pesos a los puntos del stroke
    TO DO: Cambiar la forma en que identifica a los grupos
    por el nombre
    """

    idxs = get_points_indices(stroke)
    pts = stroke.points

    C.view_layer.objects.active = gp_ob
    bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
    con = change_context(gp_ob)

    for group in gp_ob.vertex_groups:
        gp_ob.vertex_groups.active_index = group.index
        # vamos a identificar el vertex_group por el numero al final
        num_bone = get_vg_number(group.name)
        if num_bone == 'NOBONE':
            continue

        max_pt_index = idxs[num_bone+1]
        min_pt_index = idxs[num_bone]
        for idx in range(len(pts)):
            if min_pt_index <= idx <= max_pt_index:
                pts[idx].select = True
            else:
                pts[idx].select = False

        bpy.ops.gpencil.vertex_group_assign(con)
    bpy.ops.object.mode_set(mode='OBJECT')
    gp_ob.select_set(False)


def prepare_interface(armature):
    """
    Selecciona la armature, hace visible la capa de controles
    Cambia el modo a POSE
    """
    armature.select_set(True)
    armature.data.layers[0] = True
    armature.data.layers[-1] = False
    C.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')


def fit_and_add_bones(armature, gp_ob):
    stroke = gp_ob.data.layers.active.active_frame.strokes[-1]
    # TO DO: falta seleccionar el stroke
    initialized = C.window_manager.gopo_prop_group.initialized
    if not initialized:
        add_auxiliary_meshes()
    
    C.view_layer.objects.active = gp_ob
    # fit the curve
    error = C.window_manager.gopo_prop_group.error_threshold
    bpy.ops.gpencil.fit_curve(error_threshold=error, target='ARMATURE')
    obarm = armature
    bones = obarm.data.bones
    
    print(len(bones))
    pos = get_bones_positions(stroke)
    print(len(bones))
    add_deform_bones(armature, pos)
    print(len(bones))
    add_control_bones(armature, pos)
    print(len(bones))
    add_armature(gp_ob, stroke, armature)
    print(len(bones))
    add_vertex_groups(gp_ob, armature)
    print(len(bones))
    add_weights(gp_ob, stroke)
    print(len(bones))
    prepare_interface(armature)
    print(len(bones))
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------


class Gomez_OT_Poser(bpy.types.Operator):
    """ rig a grease pencil stroke"""
    bl_idname = "greasepencil.poser"
    bl_label = "Gposer Op"
    bl_options = {'REGISTER', 'UNDO'}

    bpy.types.WindowManager.gopo_prop_group = bpy.props.PointerProperty(
        type=GopoProperties)
    bpy.types.WindowManager.fitted_curve_coefs = CollectionProperty(type=FittedHandle, name='h_coefs')

    def execute(self, context):
        gp_ob = context.object
        ob_armature = context.window_manager.gopo_prop_group.ob_armature

        fit_and_add_bones(ob_armature, gp_ob)

        return {'FINISHED'}

    @classmethod
    def poll(self, context):
        """
        es greaspencil? tiene layer activa? hay frame activo? hay strokes?
        hay armature seleccionada? 
        """
        if not context.object.type == 'GPENCIL':
            return False
        if not context.object.data.layers.active:
            return False
        if not context.object.data.layers.active.active_frame:
            return False
        if not context.object.data.layers.active.active_frame.strokes:
            return False
        if not context.window_manager.gopo_prop_group.ob_armature:
            return False
        if not context.window_manager.gopo_prop_group.ob_armature.type == 'ARMATURE':
            return False

        return True


class GomezPTPanel(bpy.types.Panel):
    """
    Crear un panel en la region de la N
    """
    bl_label = "Gomez Poser"
    bl_idname = "GOMEZ_PT_layout"
    bl_space_type = "VIEW_3D"
    bl_region_type = 'UI'
    bl_category = 'Gomez Poser'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Divisiones")
        layout.use_property_split = True
        layout.row().prop(context.window_manager.gopo_prop_group, 'num_bones')
        layout.row().prop(context.window_manager.gopo_prop_group, 'num_bendy')
        layout.row().prop(context.window_manager.gopo_prop_group,
                          'ob_armature', icon='OUTLINER_OB_ARMATURE', text='Armature')
        what = layout.row().operator("greasepencil.poser")


def register():
    bpy.utils.register_class(Gomez_OT_Poser)
    bpy.utils.register_class(GomezPTPanel)


def unregister():
    bpy.utils.unregister_class(FittedHandle)
    bpy.utils.unregister_class(GopoProperties)
    bpy.utils.unregister_class(Gomez_OT_Poser)
    bpy.utils.unregister_class(GomezPTPanel)


if __name__ == "__main__":
    register()
