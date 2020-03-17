import bpy
from bpy.props import FloatProperty, IntProperty
import re
import bpy
from mathutils import Vector
import bmesh


# 2) Cambiar a la opción swing para las constraints de los huesos de deformación
# 3) Hacer que cada invocación ponga los huesos en un grupo diferente
# 4) Hacer que funcione con el objeto seleccionado y con el último stroke dibujado o con todos los strokes seleccionados.


D = bpy.data
C = bpy.context


class GopoProperties(bpy.types.PropertyGroup):
    """
    Variables de configuración de Gomez Poser
    """

    num_bones: bpy.props.IntProperty(name='gopo_num_bones', default=3, min=2)
    num_bendy: bpy.props.IntProperty(
        name='gopo_num_bendy', default=16, min=1, max=32)
    initialized: bpy.props.BoolProperty(name='initialized', default=False)
    ob_armature: bpy.props.PointerProperty(type=bpy.types.Object, poll=lambda self, object: object.type == 'ARMATURE')


bpy.utils.register_class(GopoProperties)


def add_auxiliary_meshes():
    """
    Crear objetos para reemplazar la apariencia de ctrl bones
    """
    initialized = C.window_manager.gopo_prop_group.initialized
    # Crear collection para guardar meshes auxiliares
    aux_col = bpy.data.collections.new('auxiliary_meshes')
    C.scene.collection.children.link(aux_col)
    aux_col.hide_viewport = True
    aux_col.hide_render = True
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

    initialized = True


def change_context(ob, obtype='GPENCIL'):
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
    points_indices = get_points_indices(stroke)

    bones_positions = [stroke.points[idx].co for idx in points_indices]
    return bones_positions


def add_deform_bones(armature, pos):
    armature.select_set(True)
    C.view_layer.objects.active = armature
    num_bones = C.window_manager.gopo_prop_group.num_bones
    num_bendy = C.window_manager.gopo_prop_group.num_bendy
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    ed_bones = armature.data.edit_bones
    for i in range(num_bones):
        name = 'boney-' + str(i)
        ed_bones.new(name)
        ed_bones[name].head = pos[i]
        ed_bones[name].tail = pos[i+1]
        ed_bones[name].bbone_segments = num_bendy
        ed_bones[name].use_deform = True
        ed_bones[name].roll = 0.0

        if i > 0:
            ed_bones[name].parent = ed_bones['boney-' + str(i-1)]
            ed_bones[name].use_connect = True
            ed_bones[name].inherit_scale = 'NONE'
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Y')

    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in armature.data.bones:
        if bone.name.startswith('boney'):
            bone.layers[-1] = True
            bone.layers[0] = False


def add_copy_location(armature, name, i):
    pbones = armature.pose.bones

    constr = pbones['boney-' + str(i)].constraints.new(type='COPY_LOCATION')
    constr.target = armature
    constr.subtarget = name


def add_stretch_to(armature, name, i):
    pbones = armature.pose.bones

    constr = pbones['boney-' + str(i-1)].constraints.new(type='STRETCH_TO')
    constr.target = armature
    constr.subtarget = name
    constr.keep_axis = 'SWING_Y'


def add_control_bones(armature, pos):
    armature.select_set(True)
    C.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    ed_bones = armature.data.edit_bones

    for i, p in enumerate(pos):
        name = 'ctrl_stroke_' + str(i)
        ed_bones.new(name)
        ed_bones[name].head = pos[i]
        ed_bones[name].tail = pos[i] + Vector((0.0, 0.0, 1.0))
        ed_bones[name].use_deform = False

    bpy.ops.object.mode_set(mode='OBJECT')
    for i, p in enumerate(pos):
        name = 'ctrl_stroke_' + str(i)
        # adding constraints
        if i < len(pos)-1:
            add_copy_location(armature, name, i)
        if i > 0:
            add_stretch_to(armature, name, i)

    pbones = armature.pose.bones
    for bone in pbones:
        if bone.name.startswith('ctrl'):
            bone.custom_shape = D.objects['ctrl_sphere']
            bone.custom_shape_scale = 0.5
            armature.data.bones[bone.name].show_wire = True
            armature.data.bones[bone.name].layers[0] = True
            armature.data.bones[bone.name].layers[-1] = False


def add_armature(gp_ob, stroke, armature):
    mod = gp_ob.grease_pencil_modifiers.new(type='GP_ARMATURE',
                                            name=armature.name)

    mod.object = armature
    gp_ob.vertex_groups.new(name=armature.name)
    C.view_layer.objects.active = gp_ob
    bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
    con = change_context(gp_ob)
    for pt in stroke.points:
        pt.select = True
    bpy.ops.gpencil.vertex_group_assign(con)
    mod.vertex_group = armature.name


def get_vg_number(name):
    number = re.search('(\d*)$', name).group()
    if len(number):
        return int(number)
    else:
        return 'NOBONE'


def add_vertex_groups(gp_ob, armature):
    for b in armature.data.bones:
        if b.use_deform:
            gp_ob.vertex_groups.new(name=b.name)


def add_weights(gp_ob, stroke):
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
    armature.select_set(True)
    armature.data.layers[0] = True
    armature.data.layers[-1] = False
    C.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')


def add_bones(armature, gp_ob):
    stroke = gp_ob.data.layers.active.active_frame.strokes[-1]
    initialized = C.window_manager.gopo_prop_group.initialized
    if not initialized:
        add_auxiliary_meshes()
    pos = get_bones_positions(stroke)

    add_deform_bones(armature, pos)

    add_control_bones(armature, pos)

    add_armature(gp_ob, stroke, armature)

    add_vertex_groups(gp_ob, armature)

    add_weights(gp_ob, stroke)

    prepare_interface(armature)

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

    def execute(self, context):
        gp_ob = context.object

        ob_armature = context.window_manager.gopo_prop_group.ob_armature
        add_bones(ob_armature, gp_ob)
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
    bpy.utils.unregister_class(GopoProperties)
    bpy.utils.unregister_class(Gomez_OT_Poser)
    bpy.utils.unregister_class(GomezPTPanel)


if __name__ == "__main__":
    register()
