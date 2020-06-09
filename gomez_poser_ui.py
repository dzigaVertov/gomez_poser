import bpy
from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.props import FloatVectorProperty
from bpy.props import BoolProperty, PointerProperty, CollectionProperty, StringProperty
import re
from mathutils import Vector, Matrix, kdtree
import bmesh
from . import gp_armature_applier
from .gp_armature_applier import remove_vertex_groups
from bpy_extras.view3d_utils import location_3d_to_region_2d
from math import ceil, log

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
    gp_ob: PointerProperty(type=bpy.types.Object,
                           poll=lambda self, object: object.type == 'GPENCIL')
    current_bone_group: IntProperty(default=0)
    frame_init: IntProperty(name='start_frame', default=1, min=0, max=1000000)
    frame_end: IntProperty(name='end_frame', default=1, min=0, max=1000000)
    bake_step: IntProperty(name='frame_step',
                           description='step between baked steps',
                           default=1,
                           min=1,
                           max=1000000)

    bake_to_new_layer : BoolProperty(name='bake_to_new_layer',
                                     description='Bake the stroke to new layer',
                                     default=False)
    
    bake_from_active_to_current : BoolProperty(name='from_active_to_current',
                                               description='Bake stroke from active keyframe to current frame',
                                               default=True)


def add_driver(i, def_bone, handle_left, handle_right):
    ''' Add drivers to ease properties of deform bone '''
    bone_groups = bpy.context.window_manager.gopo_prop_group.current_bone_group
    num_bones = bpy.context.window_manager.gopo_prop_group.num_bones
    armature = bpy.context.window_manager.gopo_prop_group.ob_armature

    # distances in editmode
    edit_distance_handle_left = (handle_left.head - def_bone.head).length
    edit_distance_handle_right = (handle_right.head - def_bone.tail).length

    # ease out
    deform_name = def_bone.name
    ctrl_bone = armature.pose.bones[bname(i+1, role='ctrl_stroke')]
    path_ease_out = f'pose.bones[\"{deform_name}\"].bbone_easeout'
    edit_easeout = armature.data.bones[deform_name].bbone_easeout

    # ease in
    path_ease_in = f'pose.bones[\"{deform_name}\"].bbone_easein'
    edit_easein = armature.data.bones[deform_name].bbone_easein

    # add driver easein
    driver = armature.driver_add(path_ease_in).driver
    variable = driver.variables.new()
    variable.type = 'LOC_DIFF'
    variable.name = 'varname'
    variable.targets[0].id = armature
    variable.targets[0].bone_target = def_bone.name
    variable.targets[1].id = armature
    variable.targets[1].bone_target = handle_left.name

    driver.expression = f'(varname-{edit_distance_handle_left})*{edit_easein}/{edit_distance_handle_left} '

    # add driver easeout
    # we need the control bone for this one

    driver = armature.driver_add(path_ease_out).driver
    variable = driver.variables.new()
    variable.type = 'LOC_DIFF'
    variable.name = 'varname'
    variable.targets[0].id = armature
    variable.targets[0].bone_target = ctrl_bone.name
    variable.targets[1].id = armature
    variable.targets[1].bone_target = handle_right.name

    driver.expression = f'(varname-{edit_distance_handle_left})*{edit_easein}/{edit_distance_handle_left} '


def bname(i, role='deform', side=None):
    """
    Returns the name of a bone taking into account bone_group, role, index, and side
    """
    bone_groups = bpy.context.window_manager.gopo_prop_group.current_bone_group
    name = '_'.join(str(a)
                    for a in [role, side, bone_groups, i] if a is not None)
    return name


def rig_ease(armature, i):
    """
    Adds drivers to the ease parameters of the deform bones
    driving them by the scale of the controls
    """
    num_bones = bpy.context.window_manager.gopo_prop_group.num_bones

    if i < num_bones:
        # ease in
        deform_name = bname(i)
        handle_left_name = bname(i, role='handle', side='left')
        handle_right_name = bname(i, role='handle', side='right')
        def_bone = armature.pose.bones[deform_name]
        handle_left = armature.pose.bones[handle_left_name]
        handle_right = armature.pose.bones[handle_right_name]
        add_driver(i, def_bone, handle_left, handle_right)


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
    bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=True,
                          segments=8, diameter1=0.25, depth=0.25)
    bm.to_mesh(control_cone_mesh)
    bm.free()

    ctrl_cone_ob.display_type = 'WIRE'
    bpy.context.window_manager.gopo_prop_group.initialized = True


def get_stroke_index(gp_ob):
    strokes = gp_ob.data.layers.active.active_frame.strokes
    C = bpy.context
    mode = C.mode
    if mode in {'OBJECT', 'EDIT_GPENCIL'}:
        # return the first selected
        for idx, stroke in enumerate(strokes):
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


def get_bone_world_position(bone, armature):
    """
    Calculates the position of head and tail of a bone
    in world coordinates.
    """
    arm_world_matrix = armature.matrix_world
    return arm_world_matrix @ bone.head_local, arm_world_matrix @ bone.tail_local


def calculate_points_indices_from_bones(context, stroke):
    """
    Returns the indices of the points in the stroke that constitute the
    boundaries for the deform vertex groups
    """
    group_id = stroke.bone_groups
    armature = context.window_manager.gopo_prop_group.ob_armature
    gp_ob = context.window_manager.gopo_prop_group.gp_ob
    gp_matrix = gp_ob.matrix_world
    armature_matrix = armature.matrix_world
    size = len(stroke.points)
    kd = kdtree.KDTree(size)

    for i, pt in enumerate(stroke.points):
        kd.insert(pt.co, i)

    kd.balance()

    bones = [b for b in armature.data.bones if b.use_deform and b.rigged_stroke==group_id]
    
    indices = [0]
    # TODO: add coordinate transformations
    for b in bones:
        head, tail = get_bone_world_position(b, armature)
        co, index, dist = kd.find(tail)
        indices.append(index)

    indices = sorted(indices)
    idx_pairs = list(zip(indices[:-1],indices[1:]))
    return idx_pairs
    



def get_points_indices(context, stroke):
    """
    Devuelve los índices de los puntos que corresponden
    a las posiciones de cada uno de los huesos. 
    """
    fb = context.window_manager.fitted_bones
    
    points_indices = [i.vg_idx for i in fb]

    if not points_indices:
        points_indices = calculate_points_indices_from_bones(context, stroke)
    return points_indices


def get_bones_positions(stroke):
    """
    Devuelve las posiciones de los 
    huesos a lo largo del stroke
    """
    h_coefs = bpy.context.window_manager.fitted_bones
    bones_positions = [(i.bone_head, i.bone_tail) for i in h_coefs]
    ease = [(i.ease[0], i.ease[1]) for i in h_coefs]
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

    for i, pos in enumerate(pos):
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
    handle_left = bones[bname(i, role='handle', side='left')]
    handle_right = bones[bname(i, 'handle', 'right')]
    def_bone.bbone_custom_handle_start = handle_left
    def_bone.bbone_handle_type_start = 'ABSOLUTE'
    def_bone.bbone_custom_handle_end = handle_right
    def_bone.bbone_handle_type_end = 'ABSOLUTE'

    rig_ease(armature, i)


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


def add_control_bones(armature, pos, threshold):
    """
    Adds control and handle bones in pos positions pointing up (for now) - 

    Sets to no-deform - Adds copy location and stretch-to constraints
    Adds custom shapes - Puts control bones in first layer.
    Hides handle bones
    """
    h_coefs = bpy.context.window_manager.fitted_bones
    handles = [(i.handle_l, i.handle_r) for i in h_coefs]

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
            # check if it's closed_stroke
            first_control, _ = pos[0]
            if (Vector(tail) - Vector(first_control)).length < threshold:
                edbone.parent = ed_bones[bname(0, role='ctrl_stroke')]

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
        edbone_left.inherit_scale = 'NONE'
        edbone_left.rigged_stroke = bone_groups

        edbone_right.head = h_right
        edbone_right.tail = h_right + Vector((0.0, 0.0, 1.0))
        edbone_right.use_deform = False
        edbone_right.parent = ed_bones[bname(i+1, role='ctrl_stroke')]
        edbone_right.inherit_scale = 'NONE'
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
        if i == len(pos) - 1:
            add_stretch_to(armature, bname(i+1, role='ctrl_stroke'), i+1)

        # setting handles
        add_handles(armature, i)
    # for the last control bone

    pbones = armature.pose.bones
    for bone in pbones:
        if bone.name.startswith('ctrl'):
            bone.custom_shape = bpy.data.objects['ctrl_sphere']
            bone.custom_shape_scale = 0.025
            armature.data.bones[bone.name].layers[0] = True
            armature.data.bones[bone.name].layers[-1] = False
            # TODO FIX this if bone has parent, hide it
            if bone.parent:
                bone.bone.hide = True

        if bone.name.startswith('handle'):
            bone.custom_shape = bpy.data.objects['ctrl_cone']
            bone.custom_shape_scale = 0.01
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


def add_vertex_groups(gp_ob, armature, bone_group=None):
    """
    Add a vertex group for every deform bone
    """
    if not bone_group:
        bone_group = bpy.context.window_manager.gopo_prop_group.current_bone_group
        
    name_base = 'deform_' + str(bone_group)

    for b in armature.data.bones:
        if b.use_deform and b.rigged_stroke == bone_group:
            gp_ob.vertex_groups.new(name=b.name)


def add_weights(context, gp_ob, stroke, bone_group=None):
    """
    Asigna pesos a los puntos del stroke

    """
    if not bone_group:
        bone_group = bpy.context.window_manager.gopo_prop_group.current_bone_group
    name_base = 'deform_' + str(bone_group)

    indices = get_points_indices(context, stroke)

    

    bpy.context.view_layer.objects.active = gp_ob
    bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
    

    pts = stroke.points

    def_vertex_groups = [
        group for group in gp_ob.vertex_groups if group.name.startswith(name_base)]

    for group, idx in zip(def_vertex_groups, indices):
        for point in pts:
            point.select = False
        # bpy.ops.gpencil.select_all(action='DESELECT')
        gp_ob.vertex_groups.active_index = group.index
        min_pt_index, max_pt_index = idx

        for point_idx in range(len(pts)):
            if min_pt_index <= point_idx <= max_pt_index:
                pts[point_idx].select = True
            else:
                pts[point_idx].select = False
        con = change_context(gp_ob)
        bpy.ops.gpencil.vertex_group_assign(con)
                    

    # at the end make sure all points in stroke are deselected
    for point in pts:
        point.select = False

    # TODO: change this, should not be set here
    bpy.ops.object.mode_set(mode='PAINT_GPENCIL')


def prepare_interface(armature):
    """
    Selecciona la armature, hace visible la capa de controles
    Cambia el modo a POSE
    Limpia la información de la curva fiteada
    """
    bpy.context.window_manager.fitted_bones.clear()
    bpy.ops.greasepencil.go_pose()


def fit_and_add_bones(armature, gp_ob, context, closed_threshold, error_threshold):

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
    error = error_threshold
    bpy.ops.gpencil.fit_curve(error_threshold=error,
                              target='ARMATURE',
                              stroke_index=stroke_index)

    pos, ease = get_bones_positions(stroke)
    # store the length of the chain for rigging purposes
    context.window_manager.gopo_prop_group.num_bones = len(pos)
    add_deform_bones(armature, pos, ease)
    add_control_bones(armature, pos, closed_threshold)
    add_armature(gp_ob, stroke, armature)
    add_vertex_groups(gp_ob, armature)
    add_weights(context, gp_ob, stroke)
    prepare_interface(armature)

# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------


def set_control_visibility(context, event):
    """
    Controls visibility of control and handle bones
    Makes all controls from the same stroke visible 
    if shift is pressed makes all controls visible.
    """

    pbones = context.object.pose.bones
    if not pbones:
        return
    ctrls_to_show = set(
        pbone.bone.rigged_stroke for pbone in context.selected_pose_bones)

    for pbone in pbones:

        ctrl_bone = pbone.name.startswith('ctrl')
        handle_bone = pbone.name.startswith('handle')

        if (ctrl_bone or handle_bone) and pbone.bone.rigged_stroke in ctrls_to_show:
            pbone.bone.layers[0] = True
            pbone.bone.layers[3] = True
        elif (ctrl_bone or handle_bone):
            pbone.bone.layers[0] = event.shift
            pbone.bone.layers[3] = True


def get_group_to_resample(context, gp_ob=None):
    """
    Returns stroke to be resampled, sets edit mode if coming from POSE
    """
    if not gp_ob:
        gp_ob = context.window_manager.gopo_prop_group.gp_ob

    if context.mode == 'EDIT_GPENCIL':
        for stroke in gp_ob.data.layers.active.active_frame.strokes:
            if stroke.select:
                return stroke.bone_groups
        return None

    if context.mode == 'POSE':
        if not context.active_pose_bone:
            return None

        return context.active_pose_bone.bone.rigged_stroke


class GOMEZ_OT_resample_rigged(bpy.types.Operator):
    """
    Resample a rigged stroke
    """
    bl_idname = "greasepencil.resample_rigged"
    bl_label = "Gposer resample rigged stroke"
    bl_options = {'REGISTER', 'UNDO'}

    max_dist: FloatProperty(name='max distance',
                            description='Maximum distance between consecutive points',
                            default=0.025)

    gp_ob: PointerProperty(type=bpy.types.Object,
                           name='gpencil_ob',
                           description='The Grease Pencil object to resample')

    def get_stroke_to_resample(self, context, group_id, gp_ob=None):
        if not gp_ob:
            gp_ob = bpy.context.window_manager.gopo_prop_group.gp_ob
        for layer in gp_ob.data.layers:
            for frame in layer.frames:
                for stroke in frame.strokes:
                    if stroke.bone_groups == group_id:
                        return stroke

    def get_points_indices_for_subdivide(self, context, group_id):
        depsgraph = context.evaluated_depsgraph_get()
        gp_ob = bpy.context.window_manager.gopo_prop_group.gp_ob # self.gp_ob
        
        gp_obeval = gp_ob.evaluated_get(depsgraph)
        evald_stroke = self.get_stroke_to_resample(
            context, group_id, gp_ob=gp_obeval)

        point_pairs = zip(evald_stroke.points, evald_stroke.points[1:])
        indices = []
        max_dixt = (0,0)
        for idx, pair in enumerate(point_pairs):
            point_1, point_2 = pair
            dist = (point_1.co - point_2.co).length
            if dist>max_dixt[0]:
                max_dixt = (dist, idx)
            if  dist > self.max_dist:
                divides = int(log(dist / (2*self.max_dist), 2))
                if divides > 0:
                    indices.append((idx,divides))

        return indices


    def invoke(self, context, event):
        self.gp_ob = context.window_manager.gopo_prop_group.gp_ob
        return self.execute(context)

    
    def execute(self, context):
        group_id = get_group_to_resample(context)
        gp_ob = context.window_manager.gopo_prop_group.gp_ob
        if not group_id:
            return {'CANCELLED'}

        indices = self.get_points_indices_for_subdivide(context, group_id)
        if not indices:
            return {'FINISHED'}

        original_mode = context.mode
        
        context.view_layer.objects.active = gp_ob
        bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
        bpy.ops.gpencil.select_all(action='DESELECT')
        stroke = self.get_stroke_to_resample(context, group_id)
        
        for idx, times in reversed(indices):
            first_point = stroke.points[idx]
            second_point = stroke.points[idx + 1]
            first_point.select = True
            second_point.select = True
            for _ in range(times):
                bpy.ops.gpencil.stroke_subdivide()
            bpy.ops.gpencil.select_all(action='DESELECT')

        remove_vertex_groups(gp_ob, group_id) # vertex groups need to be rebuilt
        
        armature = context.window_manager.gopo_prop_group.ob_armature
        add_vertex_groups(gp_ob,armature, bone_group=group_id )
        add_weights(context,gp_ob, stroke, bone_group=group_id)

        if original_mode== 'POSE':
            bpy.ops.object.mode_set(mode='OBJECT')
            armature.select_set(True)
            context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='POSE')
            
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        if not ((context.mode == 'POSE') or (context.mode == 'EDIT_GPENCIL')):
                return False
        return True
        
        



class GOMEZ_OT_go_pose(bpy.types.Operator):
    """
    Go from draw mode of the gp_ob  to pose mode of the armature
    """
    bl_idname = "greasepencil.go_pose"
    bl_label = "Gposer go_pose"
    bl_options = {'REGISTER', 'UNDO'}

    def modal(self, context, event):
        if not context.active_object.type == 'ARMATURE':
            return {'FINISHED'}
        if event.shift and event.type == 'O':
            bpy.ops.armature.go_draw()
            return {'FINISHED'}
        set_control_visibility(context, event)

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        armature = context.window_manager.gopo_prop_group.ob_armature
        armature.hide_viewport = False
        armature.select_set(True)
        context.space_data.overlay.show_relationship_lines = False
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

    closed_stroke_threshold: FloatProperty(name='closed_stroke_threshold', default=0.03)
    error_threshold: FloatProperty(name='error_threshold', default=0.01)

    def invoke(self, context, event):
        if context.object.type == 'GPENCIL':
            context.window_manager.gopo_prop_group.current_bone_group += 1
            context.window_manager.gopo_prop_group.gp_ob = context.object
            self.error_threshold = context.window_manager.gopo_prop_group.error_threshold
            return self.execute(context)
        return {'CANCELLED'}

    def execute(self, context):
        if 'ctrl_sphere' not in bpy.data.objects:
            context.window_manager.gopo_prop_group.initialized = False
        if context.mode == 'POSE':
            bpy.ops.object.mode_set(mode='OBJECT')
            gp_ob = context.window_manager.gopo_prop_group.gp_ob
            context.view_layer.objects.active = gp_ob

        gp_ob = context.object
        ob_armature = context.window_manager.gopo_prop_group.ob_armature

        fit_and_add_bones(ob_armature, gp_ob, context,
                          self.closed_stroke_threshold, self.error_threshold)

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
        addon_properties = context.window_manager.gopo_prop_group
        layout = self.layout
        layout.label(text="Divisiones")
        layout.use_property_split = True

        layout.row().prop(addon_properties, 'error_threshold')

        layout.row().prop(addon_properties, 'num_bendy')

        layout.row().prop(addon_properties,
                          'ob_armature',
                          icon='OUTLINER_OB_ARMATURE',
                          text='Armature')

        layout.row().prop(addon_properties,
                          'gp_ob',
                          icon='OUTLINER_OB_GREASEPENCIL',
                          text='gpencil')
        
        what = layout.row().operator("greasepencil.poser")

        layout.column()

        layout.row().prop(addon_properties, 'frame_init')
        layout.row().prop(addon_properties, 'frame_end')
        layout.row().prop(addon_properties, 'bake_step')
        layout.row().prop(addon_properties, 'bake_to_new_layer')
        layout.row().prop(addon_properties, 'bake_from_active_to_current')
        layout.row().operator("greasepencil.gp_bake_animation")


def register():
    bpy.utils.register_class(GopoProperties)
    bpy.utils.register_class(FittedBone)
    bpy.utils.register_class(Gomez_OT_Poser)
    bpy.utils.register_class(GomezPTPanel)
    bpy.utils.register_class(GOMEZ_OT_go_draw)
    bpy.utils.register_class(GOMEZ_OT_go_pose)
    bpy.utils.register_class(GOMEZ_OT_resample_rigged)

    bpy.types.WindowManager.gopo_prop_group = PointerProperty(
        type=GopoProperties)
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
        kmi = km.keymap_items.new(
            'greasepencil.poser', type='P', value='PRESS', shift=True)
        kmj = km.keymap_items.new(
            'armature.go_draw', type='O', value='PRESS', shift=True)
        kml = km.keymap_items.new(
            'greasepencil.go_pose', type='L', value='PRESS', shift=True)
        kmll = km.keymap_items.new(
            'armature.select_all_ctrls', type='L', value='PRESS', shift=True, ctrl=True)
        kmrr = km.keymap_items.new(
            'greasepencil.resample_rigged', type='R', value='PRESS',shift=True,  ctrl=True)
        kmbb = km.keymap_items.new(
            'greasepencil.gp_bake_animation', type='B', value='PRESS', shift=True, ctrl=True)
        
        addon_keymaps.append((km, kmi))
        addon_keymaps.append((km, kmj))
        addon_keymaps.append((km, kml))
        addon_keymaps.append((km, kmll))
        addon_keymaps.append((km, kmrr))
        addon_keymaps.append((km, kmbb))

        
def unregister():
    bpy.utils.unregister_class(FittedBone)
    bpy.utils.unregister_class(GopoProperties)
    bpy.utils.unregister_class(Gomez_OT_Poser)
    bpy.utils.unregister_class(GomezPTPanel)
    bpy.utils.unregister_class(GOMEZ_OT_go_draw)
    bpy.utils.unregister_class(GOMEZ_OT_go_pose)
    bpy.utils.unregister_class(GOMEZ_OT_resample_rigged)

    del bpy.types.WindowManager.gopo_prop_group
    del bpy.types.WindowManager.fitted_bones
    del bpy.types.Bone.rigged_stroke
    del bpy.types.EditBone.rigged_stroke

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


if __name__ == "__main__":
    register()
