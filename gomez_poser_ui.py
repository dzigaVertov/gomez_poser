import bpy
from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.props import FloatVectorProperty
from bpy.props import BoolProperty,PointerProperty, CollectionProperty, StringProperty
import re
from mathutils import Vector, Matrix
import bmesh
from . import gp_armature_applier
from bpy_extras.view3d_utils import location_3d_to_region_2d


# KEYMAP HANDLING
addon_keymaps = []

class FittedBone(bpy.types.PropertyGroup):
    """
    Grupo donde se guardan los datos de la curva fiteada. 
    """
    handle_l: bpy.props.FloatVectorProperty()
    bone_head: bpy.props.FloatVectorProperty()
    bone_tail: bpy.props.FloatVectorProperty()
    handle_r: bpy.props.FloatVectorProperty()
    ease: bpy.props.FloatVectorProperty(size=2)
    vg_idx: bpy.props.IntVectorProperty(size=2)



class GopoProperties(bpy.types.PropertyGroup):
    """
    Variables de configuración de Gomez Poser
    """
    
    error_threshold: FloatProperty(default=0.01)
    num_bones: IntProperty(name='gopo_num_bones',
                           default=3,
                           min=0)
    num_bendy: IntProperty(name='gopo_num_bendy',
                           default=32,
                           min=1,
                           max=32)
    initialized: BoolProperty(name='initialized',
                              default=False)
    ob_armature: PointerProperty(type=bpy.types.Object,
                                 poll=lambda self, object: object.type == 'ARMATURE')
    gp_ob : PointerProperty(type=bpy.types.Object,
                            poll=lambda self, object: object.type == 'GPENCIL')
    current_bone_group: IntProperty(default=0)
    frame_init : IntProperty(name='start_frame', default=1, min=0, max=1000000)
    frame_end : IntProperty(name='end_frame', default=1, min=0, max=1000000)
    bake_step : IntProperty(name='frame_step',
                       description='step between baked steps',
                       default=1,
                       min=1,
                       max=1000000)

    
def add_driver(source, target, prop, func = str, transform_type=None, source_bone=None, var_type='TRANSFORMS'):
    ''' Add driver to source prop (at index), driven by target dataPath '''

    driver = source.driver_add( prop ).driver

    variable = driver.variables.new()
    variable.type = 'TRANSFORMS'
    variable.name                 = 'varname'
    variable.targets[0].id        = target
    if source_bone:
        variable.targets[0].bone_target = source_bone
    if transform_type:
        variable.targets[0].transform_type = transform_type

    driver.expression = func(variable.name) 



def bname(i, role='deform', side=None):
    """
    Returns the name of a bone taking into account bone_group, role, index, and side
    """
    bone_groups = bpy.context.window_manager.gopo_prop_group.current_bone_group
    name = '_'.join(str(a) for a in [role, side, bone_groups, i] if a is not None)
    return name

def rig_ease(armature, ctrl_name, i):
    """
    Adds drivers to the ease parameters of the deform bones
    driving them by the scale of the controls
    """
    bone_groups = bpy.context.window_manager.gopo_prop_group.current_bone_group
    num_bones = bpy.context.window_manager.gopo_prop_group.num_bones
    if i > 0:
        # ease out
        deform_name = bname(i-1)
        path_to_ease = f'pose.bones[\"{deform_name}\"].bbone_easeout'
        
        edit_easeout = armature.data.bones[deform_name].bbone_easeout
        func = lambda x: f'max(-{edit_easeout}, 3*({x}-1))'
        add_driver(armature,
                   armature,
                   path_to_ease,
                   func=func,
                   transform_type='SCALE_AVG',
                   source_bone=ctrl_name)
    if i < num_bones:
        # ease in
        deform_name = bname(i)
        path_to_ease = f'pose.bones[\"{deform_name}\"].bbone_easein'
        edit_easein = armature.data.bones[deform_name].bbone_easein
        func = lambda x: f'max(-{edit_easein}, 3*({x}-1))'
        add_driver(armature,
                   armature,
                   path_to_ease,
                   func=func,
                   transform_type='SCALE_AVG',
                   source_bone=ctrl_name)
    

def add_auxiliary_meshes():
    """
    Crear objetos para reemplazar la apariencia de ctrl bones
    """
    initialized = bpy.context.window_manager.gopo_prop_group.initialized
    if initialized:
        return
    
    # Crear collection para guardar meshes auxiliares
    aux_col = bpy.data.collections.new('auxiliary_meshes')
    bpy.context.scene.collection.children.link(aux_col)
    aux_col.hide_viewport = True
    aux_col.hide_render = True

    # ESFERA
    # Crear objeto y mesh vacíos
    control_sphere_mesh = bpy.data.meshes.new('ctrl_sphere')
    ctrl_sphere_ob = bpy.data.objects.new('ctrl_sphere', control_sphere_mesh)
    # Linkear objeto a collection, hacer activo
    aux_col.objects.link(ctrl_sphere_ob)
    ctrl_sphere_ob.select_set(True)
    bpy.context.view_layer.objects.active = ctrl_sphere_ob

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
    bpy.context.view_layer.objects.active = ctrl_cone_ob

    # Crear geometría
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=True, segments= 8, diameter1=0.25, depth=0.25)
    bm.to_mesh(control_cone_mesh)
    bm.free()

    ctrl_cone_ob.display_type = 'WIRE'
    initialized = True


def get_stroke_index(gp_ob):
    strokes = gp_ob.data.layers.active.active_frame.strokes
    C = bpy.context
    mode = C.mode
    if mode in {'OBJECT', 'EDIT_GPENCIL'}:
        # return the first selected
        for idx,stroke in enumerate(strokes):
            if stroke.select:
                return idx
    # in any other case return the last stroke
    return -1
    
    
def change_context(ob, obtype='GPENCIL'):
    """
    Modificar el contexto para cambiar los pesos
    de los vertex groups de grease pencil
    """
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            break
    for region in area.regions:
        if region.type == "WINDOW":
            break

    space = area.spaces[0]
    con = bpy.context.copy()
    con['area'] = area
    con['region'] = region
    con['space_data'] = space
    if obtype == 'GPENCIL':
        con['active_gpencil_frame'] = ob.data.layers.active.active_frame
        con['editable_gpencil_layers'] = ob.data.layers
    elif obtype == 'ARMATURE':
        con['active_object'] = ob

    return con


def get_points_indices(stroke):
    """
    Devuelve los índices de los puntos que corresponden
    a las posiciones de cada uno de los huesos. 
    """
    fb = bpy.context.window_manager.fitted_bones
    points_indices = [i.vg_idx for i in fb]
    return points_indices


def get_bones_positions(stroke):
    """
    Devuelve las posiciones de los 
    huesos a lo largo del stroke
    """
    h_coefs = bpy.context.window_manager.fitted_bones
    bones_positions = [(i.bone_head, i.bone_tail) for i in h_coefs]
    ease = [(i.ease[0], i.ease[1]) for i in h_coefs ]
    return bones_positions, ease


def add_deform_bones(armature, pos, ease):
    """
    Creates deform bones - Puts bones in positions
    Creates the hierarchy - Calculates roll
    Sets stroke_id
    Puts Deform bones in last layer    
    """
    
    armature.select_set(True)
    armature.hide_viewport = False
    bpy.context.view_layer.objects.active = armature
    bone_group_id = bpy.context.window_manager.gopo_prop_group.current_bone_group
    num_bendy = bpy.context.window_manager.gopo_prop_group.num_bendy

    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    ed_bones = armature.data.edit_bones

    for i,pos in enumerate(pos):
        head, tail = pos
        ease_in, ease_out = ease[i]
        name = bname(i)
        
        edbone = ed_bones.new(name)
        edbone.head = head
        edbone.tail = tail
        edbone.bbone_segments = num_bendy
        edbone.use_deform = True
        edbone.roll = 0.0
        edbone.bbone_easein = ease_in
        edbone.bbone_easeout = ease_out
        edbone.rigged_stroke = bone_group_id

        if i > 0:
            edbone.parent = ed_bones[bname(i-1)]
            edbone.use_connect = True
            edbone.inherit_scale = 'NONE'
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Y', axis_only=True)

    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in armature.data.bones:
        if bone.name.startswith('deform'):
            bone.layers[-1] = True
            bone.layers[0] = False

def add_handles(armature, i):
    """
    Sets handle bones as bezier handles for the deform bone
    """
    bones = armature.data.bones
    def_bone = bones[bname(i)]
    def_bone.bbone_custom_handle_start = bones[bname(i,role='handle',side='left')]
    def_bone.bbone_handle_type_start = 'ABSOLUTE'
    def_bone.bbone_custom_handle_end = bones[bname(i, 'handle', 'right')]
    def_bone.bbone_handle_type_end = 'ABSOLUTE'

def add_copy_location(armature, subtarget, i):
    """
    Adds a copy location contraint to the i-th bone
    targeting the "name" bone
    """
    pbones = armature.pose.bones
        
    constr = pbones[bname(i)].constraints.new(type='COPY_LOCATION')
    constr.target = armature
    constr.subtarget = subtarget


def add_stretch_to(armature, subtarget, i):
    """
    Adds a stretch-to contraint to the i-th bone
    targeting the "name" bone
    """
    pbones = armature.pose.bones

    constr = pbones[bname(i-1)].constraints.new(type='STRETCH_TO')
    constr.target = armature
    constr.subtarget = subtarget
    constr.keep_axis = 'SWING_Y'


def add_control_bones(armature, pos):
    """
    Adds control and handle bones in pos positions pointing up (for now) - 

    Sets to no-deform - Adds copy location and stretch-to constraints
    Adds custom shapes - Puts control bones in first layer.
    Hides handle bones
    """
    h_coefs = bpy.context.window_manager.fitted_bones
    handles = [(i.handle_l, i.handle_r) for i in h_coefs ]
    
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    ed_bones = armature.data.edit_bones
    bone_groups = bpy.context.window_manager.gopo_prop_group.current_bone_group
    
    # add the knots
    for i, p in enumerate(pos):
        name = bname(i, role='ctrl_stroke')
        ctrl, tail = p
        edbone = ed_bones.new(name)
        edbone.head = Vector(ctrl)
        edbone.tail = Vector(ctrl) + Vector((0.0, 0.0, 1.0))
        edbone.use_deform = False
        edbone.rigged_stroke = bone_groups

        # The tail of the last bone gets a knot
        if i == len(pos)-1:
            name = bname(i+1, role='ctrl_stroke')
            edbone = ed_bones.new(name)
            edbone.head = Vector(tail)
            edbone.tail = Vector(tail) + Vector((0.0, 0.0, 1.0))
            edbone.use_deform = False
            edbone.rigged_stroke = bone_groups

        
    for i, h in enumerate(handles):
        h_left, h_right = map(Vector, h)
        name_left = bname(i, role='handle', side='left')
        name_right = bname(i, role='handle', side='right')
        edbone_left = ed_bones.new(name_left)
        edbone_right = ed_bones.new(name_right)
        
        edbone_left.head = h_left
        edbone_left.tail = h_left + Vector((0.0, 0.0, 1.0))
        edbone_left.use_deform = False
        edbone_left.parent = ed_bones[bname(i, role='ctrl_stroke')]
        edbone.rigged_stroke = bone_groups

        edbone_right.head = h_right
        edbone_right.tail = h_right + Vector((0.0, 0.0, 1.0))
        edbone_right.use_deform = False
        edbone_right.parent = ed_bones[bname(i+1, role='ctrl_stroke')]
        edbone_right.rigged_stroke = bone_groups


    bpy.ops.object.mode_set(mode='OBJECT')
    for i, p in enumerate(pos):
        name = bname(i, role='ctrl_stroke')
        bone = armature.data.bones[name]
        
        # adding constraints
        if i < len(pos):
            add_copy_location(armature, name, i)
        if i > 0:
            add_stretch_to(armature, name, i)
        if i == len(pos) -1:
            add_stretch_to(armature, bname(i+1, role='ctrl_stroke'), i+1)

        rig_ease(armature, name, i)

        # setting handles
        add_handles(armature, i)
    # for the last control bone
    rig_ease(armature, bname(len(pos), role='ctrl_stroke'), len(pos))

    pbones = armature.pose.bones
    for bone in pbones:
        if bone.name.startswith('ctrl'):
            bone.custom_shape = bpy.data.objects['ctrl_sphere']
            bone.custom_shape_scale = 0.1
            armature.data.bones[bone.name].show_wire = True
            armature.data.bones[bone.name].layers[0] = True
            armature.data.bones[bone.name].layers[-1] = False
            

        if bone.name.startswith('handle'):
            bone.custom_shape = bpy.data.objects['ctrl_cone']
            bone.custom_shape_scale = 0.05
            armature.data.bones[bone.name].show_wire = True
            armature.data.bones[bone.name].layers[1] = True
            armature.data.bones[bone.name].layers[0] = False
            armature.data.bones[bone.name].layers[-1] = False
        


def add_armature(gp_ob, stroke, armature):
    """
    Adds an armature modifier to the greasepencil object
    Adds a new vertex group containing the stroke
    Sets the modifier to affect only that vertex group
    """
    bone_group = bpy.context.window_manager.gopo_prop_group.current_bone_group
    name = armature.name + str(bone_group)
    mod = gp_ob.grease_pencil_modifiers.new(type='GP_ARMATURE',
                                            name=name)

    mod.object = armature

    bpy.context.view_layer.objects.active = gp_ob
    bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
    bpy.ops.gpencil.select_all(action='DESELECT')

    for pt in stroke.points:
        pt.select = True

    con = change_context(gp_ob)
    gp_ob.vertex_groups.new(name=name)
    bpy.ops.gpencil.vertex_group_assign(con)
    mod.vertex_group = name

    
def add_vertex_groups(gp_ob, armature):
    """
    Add a vertex group for every deform bone
    """
    bone_group = bpy.context.window_manager.gopo_prop_group.current_bone_group
    name_base = 'deform_' + str(bone_group)
    
    for b in armature.data.bones:
        if b.use_deform and b.name.startswith(name_base):
            gp_ob.vertex_groups.new(name=b.name)


def add_weights(gp_ob, stroke):
    """
    Asigna pesos a los puntos del stroke

    """
    bone_group = bpy.context.window_manager.gopo_prop_group.current_bone_group
    name_base = 'deform_' + str(bone_group)

    indices = get_points_indices(stroke)
    pts = stroke.points

    bpy.context.view_layer.objects.active = gp_ob
    bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
    con = change_context(gp_ob)

    def_vertex_groups = [group for group in gp_ob.vertex_groups if group.name.startswith(name_base)]

    for group, idx in zip(def_vertex_groups, indices):
        
        gp_ob.vertex_groups.active_index = group.index
        min_pt_index, max_pt_index = idx
        
        for point_idx in range(len(pts)):
            if min_pt_index <= point_idx <= max_pt_index:
                pts[point_idx].select = True
            else:
                pts[point_idx].select = False

        bpy.ops.gpencil.vertex_group_assign(con)

    # at the end make sure all points in stroke are deselected
    for point in pts:
        point.select = False
        
    bpy.ops.object.mode_set(mode='OBJECT')
    gp_ob.select_set(False)


def prepare_interface(armature):
    """
    Selecciona la armature, hace visible la capa de controles
    Cambia el modo a POSE
    Limpia la información de la curva fiteada
    """
    armature.select_set(True)
    armature.data.layers[0] = True
    armature.data.layers[-1] = False
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.context.window_manager.fitted_bones.clear() 


def fit_and_add_bones(armature, gp_ob, context):

    # Get and initialize stroke to be rigged
    group_id = context.window_manager.gopo_prop_group.current_bone_group
    stroke_index = get_stroke_index(gp_ob)
    stroke = gp_ob.data.layers.active.active_frame.strokes[stroke_index]
    
    stroke.bone_groups = group_id

    # TODO move this away from here
    initialized = context.window_manager.gopo_prop_group.initialized
    if not initialized:
        add_auxiliary_meshes()
    
    context.view_layer.objects.active = gp_ob
    # fit the curve
    error = context.window_manager.gopo_prop_group.error_threshold
    bpy.ops.gpencil.fit_curve(error_threshold=error,
                              target='ARMATURE',
                              stroke_index=stroke_index)
    
    pos, ease = get_bones_positions(stroke)
    # store the length of the chain for rigging purposes
    bpy.context.window_manager.gopo_prop_group.num_bones = len(pos)
    add_deform_bones(armature, pos, ease)
    add_control_bones(armature, pos)
    add_armature(gp_ob, stroke, armature)
    add_vertex_groups(gp_ob, armature)
    add_weights(gp_ob, stroke)
    prepare_interface(armature)

# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def set_control_visibility(context, event):
    mo = Vector((event.mouse_region_x, event.mouse_region_y))
    bones = context.object.data.bones
    pbones = context.object.pose.bones
    for bone, pbone in zip(bones, pbones):
        if bone.name.startswith('ctrl') and (mo-location_3d_to_region_2d(context.region, context.space_data.region_3d, pbone.head)).length < 200:
            bone.layers[0] = True
            bone.layers[3] = False
        else:
            bone.layers[0] = False
            bone.layers[3] = True
 
    
class GOMEZ_OT_go_pose(bpy.types.Operator):
    """
    Go from draw mode of the gp_ob  to pose mode of the armature
    """
    bl_idname = "greasepencil.go_pose"
    bl_label = "Gposer go_pose"
    bl_options = {'REGISTER', 'UNDO'}

    def modal(self, context, event):
        if event.shift and event.type == 'O':
            return {'FINISHED'}
        set_control_visibility(context, event)
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        bpy.ops.object.mode_set(mode='OBJECT')
        armature = context.window_manager.gopo_prop_group.ob_armature
        armature.hide_viewport = False
        armature.select_set(True)
        # deselect the gp object
        context.view_layer.objects.active.select_set(False)
        context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='POSE')
        context.window_manager.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}

    @classmethod
    def poll(cls, context):
        armature = context.window_manager.gopo_prop_group.ob_armature
        if context.mode == 'PAINT_GPENCIL' and armature:
            return True
        else:
            return False

# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------        
        
class GOMEZ_OT_go_draw(bpy.types.Operator):
    """
    Go from pose mode to draw mode of the grease pencil object
    """
    bl_idname = "armature.go_draw"
    bl_label = "Gposer go_draw"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return self.execute(context)
        
    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        gp_ob = context.window_manager.gopo_prop_group.gp_ob
        gp_ob.select_set(True)
        # hide the armature
        context.object.hide_viewport = True
        context.view_layer.objects.active = gp_ob
        bpy.ops.object.mode_set(mode='PAINT_GPENCIL')
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        gp_ob = context.window_manager.gopo_prop_group.gp_ob
        if context.mode == 'POSE' and gp_ob:
            return True
        else:
            return False
            
        
        

class Gomez_OT_Poser(bpy.types.Operator):
    """
    Rig a grease pencil stroke
    """
    bl_idname = "greasepencil.poser"
    bl_label = "Rig Stroke"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.object.type == 'GPENCIL':
            context.window_manager.gopo_prop_group.current_bone_group +=1
            context.window_manager.gopo_prop_group.gp_ob = context.object
            return self.execute(context)
        return {'CANCELLED'}

    def execute(self, context):
        if context.mode == 'POSE':
            bpy.ops.object.mode_set(mode='OBJECT')
            gp_ob = context.window_manager.gopo_prop_group.gp_ob
            context.view_layer.objects.active = gp_ob
            
        gp_ob = context.object
        ob_armature = context.window_manager.gopo_prop_group.ob_armature
        
        fit_and_add_bones(ob_armature, gp_ob, context)

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        """
        es greaspencil? tiene layer activa? hay frame activo? hay strokes?
        hay armature seleccionada? 
        """
        if not context.window_manager.gopo_prop_group.ob_armature:
            return False
        if not context.window_manager.gopo_prop_group.ob_armature.type == 'ARMATURE':
            return False
        if not context.object:
            return False
        if context.object.type == 'GPENCIL':
            if not context.object.data.layers.active:
                return False
            if not context.object.data.layers.active.active_frame:
                return False
            if not context.object.data.layers.active.active_frame.strokes:
                return False
            return True
        elif context.object.type == 'ARMATURE':
            gp_ob = context.window_manager.gopo_prop_group.gp_ob
            if context.mode == 'POSE' and gp_ob:
                return True

        return False


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
        layout.row().prop(context.window_manager.gopo_prop_group, 'error_threshold')
        layout.row().prop(context.window_manager.gopo_prop_group, 'num_bendy')
        layout.row().prop(context.window_manager.gopo_prop_group,
                          'ob_armature', icon='OUTLINER_OB_ARMATURE', text='Armature')
        layout.row().prop(context.window_manager.gopo_prop_group, 'gp_ob', icon='OUTLINER_OB_GREASEPENCIL',text='gpencil')
        what = layout.row().operator("greasepencil.poser")

        layout.column()
        
        layout.row().prop(context.window_manager.gopo_prop_group, 'frame_init')
        layout.row().prop(context.window_manager.gopo_prop_group, 'frame_end')
        layout.row().prop(context.window_manager.gopo_prop_group, 'bake_step')
        layout.row().operator("greasepencil.gp_bake_animation")
        


def register():
    bpy.utils.register_class(GopoProperties)
    bpy.utils.register_class(FittedBone)
    bpy.utils.register_class(Gomez_OT_Poser)
    bpy.utils.register_class(GomezPTPanel)
    bpy.utils.register_class(GOMEZ_OT_go_draw)
    bpy.utils.register_class(GOMEZ_OT_go_pose)

    
    bpy.types.WindowManager.gopo_prop_group = PointerProperty(type=GopoProperties)
    bpy.types.WindowManager.fitted_bones = CollectionProperty(type=FittedBone,
                                                              name='h_coefs')
    bpy.types.Bone.rigged_stroke = IntProperty(name='stroke_id',
                                             description='id of linked stroke',
                                               default=0)
    bpy.types.EditBone.rigged_stroke = IntProperty(name='stroke_id',
                                             description='id of linked stroke',
                                               default=0)
    
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('greasepencil.poser', type='P', value='PRESS', shift=True)
        kmj = km.keymap_items.new('armature.go_draw', type='O', value='PRESS', shift = True)
        kml = km.keymap_items.new('greasepencil.go_pose', type='L',value='PRESS', shift=True)
        addon_keymaps.append((km, kmi))
        addon_keymaps.append((km, kmj))
        addon_keymaps.append((km, kml))




def unregister():
    bpy.utils.unregister_class(FittedBone)
    bpy.utils.unregister_class(GopoProperties)
    bpy.utils.unregister_class(Gomez_OT_Poser)
    bpy.utils.unregister_class(GomezPTPanel)
    bpy.utils.unregister_class(GOMEZ_OT_go_draw)
    bpy.utils.unregister_class(GOMEZ_OT_go_pose)
        
    del bpy.types.WindowManager.gopo_prop_group
    del bpy.types.WindowManager.fitted_bones
    del bpy.types.Bone.rigged_stroke
    del bpy.types.EditBone.rigged_stroke

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

if __name__ == "__main__":
    register()
