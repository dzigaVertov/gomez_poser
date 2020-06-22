'''
Copyright (C) 2020 dzigaVertov@github
gomezmarcelod@gmail.com

Created by Marcelo Demian Gómez

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
import bpy
from mathutils import Vector, Matrix, kdtree
from bpy.props import FloatProperty, IntProperty, FloatVectorProperty, BoolProperty, PointerProperty, CollectionProperty, StringProperty
from . import gp_auxiliary_objects


def get_bone(bones, rigged_stroke, bone_type, bone_order):
   
    for b in bones:
        databone = b.bone if type(b) == bpy.types.PoseBone else b
        if databone.rigged_stroke == rigged_stroke and databone.bone_type==bone_type and databone.bone_order == bone_order:
            return b


def add_driver(i, def_bone, handle_left, handle_right, group_id):
    ''' Add drivers to ease properties of deform bone '''
    
    num_bones = bpy.context.window_manager.gopo_prop_group.num_bones
    armature = bpy.context.window_manager.gopo_prop_group.ob_armature

    # distances in editmode
    # TODO: this looks dangerous: the bones passed to this function are posebones
    edit_distance_handle_left = (handle_left.head - def_bone.head).length
    edit_distance_handle_right = (handle_right.head - def_bone.tail).length

    # ease out
    deform_name = def_bone.name
    ctrl_bone = get_bone(armature.pose.bones, group_id, 'CTRL', i+1 )
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


def rig_ease(armature, i, group_id):
    """
    Adds drivers to the ease parameters of the deform bones
    driving them by the scale of the controls
    """
    num_bones = bpy.context.window_manager.gopo_prop_group.num_bones

    if i < num_bones:
        # ease in
        def_bone = get_bone(armature.pose.bones, group_id, 'DEFORM', i)  
        handle_left = get_bone(armature.pose.bones, group_id, 'HANDLE_LEFT', i)  
        handle_right = get_bone(armature.pose.bones, group_id, 'HANDLE_RIGHT', i)  
        add_driver(i, def_bone, handle_left, handle_right, group_id)


def get_stroke_index(gp_ob):
    """
    Returns the index of either the first selected stroke or the last one added
    """
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

    bones = [
        b for b in armature.data.bones if b.use_deform and b.rigged_stroke == group_id]

    indices = [0]
    # TODO: add coordinate transformations
    for b in bones:
        head, tail = get_bone_world_position(b, armature)
        co, index, dist = kd.find(tail)
        indices.append(index)

    indices = sorted(indices)
    idx_pairs = list(zip(indices[:-1], indices[1:]))
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


def get_bones_positions(context):
    """
    Devuelve las posiciones de los 
    huesos a lo largo del stroke
    """
    h_coefs = context.window_manager.fitted_bones
    bones_positions = [(i.bone_head, i.bone_tail) for i in h_coefs]
    ease = [(i.ease[0], i.ease[1]) for i in h_coefs]
    return bones_positions, ease


def add_deform_bones(armature, pos, ease, group_id):
    """
    Creates deform bones - Puts bones in positions
    Creates the hierarchy - Calculates roll
    Sets stroke_id
    Puts Deform bones in last layer    
    """
    armature.select_set(True)
    armature.hide_viewport = False
    bpy.context.view_layer.objects.active = armature
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
        edbone.rigged_stroke = group_id
        edbone.bone_type = 'DEFORM'
        edbone.bone_order = i

        if i > 0:
            edbone.parent = get_bone(ed_bones, group_id, 'DEFORM', i-1)
            edbone.use_connect = True
            edbone.inherit_scale = 'NONE'
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Y', axis_only=True)

    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in armature.data.bones:
        if bone.bone_type == 'DEFORM':
            bone.layers[-1] = True
            bone.layers[0] = False


def add_handles(armature, i, group_id):
    """
    Sets handle bones as bezier handles for the deform bone
    """
    bones = armature.data.bones
    def_bone = get_bone(bones, group_id, 'DEFORM', i )
    handle_left = get_bone(bones, group_id, 'HANDLE_LEFT', i )
    handle_right = get_bone(bones, group_id, 'HANDLE_RIGHT', i )
    def_bone.bbone_custom_handle_start = handle_left
    def_bone.bbone_handle_type_start = 'ABSOLUTE'
    def_bone.bbone_custom_handle_end = handle_right
    def_bone.bbone_handle_type_end = 'ABSOLUTE'

    rig_ease(armature, i, group_id)


def add_copy_location(armature, subtarget, i, group_id):
    """
    Adds a copy location contraint to the i-th bone
    targeting the "name" bone
    """
    pbones = armature.pose.bones

    constr = get_bone(pbones, group_id, 'DEFORM', i ).constraints.new(type='COPY_LOCATION')
    constr.target = armature
    constr.subtarget = subtarget


def add_stretch_to(armature, subtarget_name, i, group_id):
    """
    Adds a stretch-to contraint to the i-th bone
    targeting the "subtarget_name" bone
    """
    pbones = armature.pose.bones
    def_bone = get_bone(pbones, group_id,'DEFORM', i-1) 
    constr = def_bone.constraints.new(type='STRETCH_TO')
    constr.target = armature
    constr.subtarget = subtarget_name
    constr.keep_axis = 'SWING_Y'


def add_control_bones(armature, pos, threshold, group_id):
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
    
    # add the knots
    for i, p in enumerate(pos):
        name = bname(i, role='ctrl_stroke')
        ctrl, tail = p
        edbone = ed_bones.new(name)
        edbone.head = Vector(ctrl)
        edbone.tail = Vector(ctrl) + Vector((0.0, 0.0, 1.0))
        edbone.use_deform = False
        edbone.rigged_stroke = group_id
        edbone.bone_type = 'CTRL'
        edbone.bone_order = i 

        # The tail of the last bone gets a knot
        if i == len(pos)-1:
            name = bname(i+1, role='ctrl_stroke')
            edbone = ed_bones.new(name)
            edbone.head = Vector(tail)
            edbone.tail = Vector(tail) + Vector((0.0, 0.0, 1.0))
            edbone.use_deform = False
            edbone.rigged_stroke = group_id
            edbone.bone_type = 'CTRL'
            edbone.bone_order = i+1
            # check if it's closed_stroke
            first_control, _ = pos[0]
            if (Vector(tail) - Vector(first_control)).length < threshold:
                edbone.parent = get_bone(ed_bones, group_id, 'CTRL', 0)

    # Add the handles
    for i, h in enumerate(handles):
        h_left, h_right = map(Vector, h)
        name_left = bname(i, role='handle', side='left')
        name_right = bname(i, role='handle', side='right')
        edbone_left = ed_bones.new(name_left)
        edbone_right = ed_bones.new(name_right)

        edbone_left.head = h_left
        edbone_left.tail = h_left + Vector((0.0, 0.0, 1.0))
        edbone_left.use_deform = False
        edbone_left.parent = get_bone(ed_bones, group_id, 'CTRL', i)
        edbone_left.inherit_scale = 'NONE'
        edbone_left.rigged_stroke = group_id
        edbone_left.bone_type = 'HANDLE_LEFT'
        edbone_left.bone_order = i

        edbone_right.head = h_right
        edbone_right.tail = h_right + Vector((0.0, 0.0, 1.0))
        edbone_right.use_deform = False
        edbone_right.parent = get_bone(ed_bones, group_id, 'CTRL', i+1)
        edbone_right.inherit_scale = 'NONE'
        edbone_right.rigged_stroke = group_id
        edbone_right.bone_type = 'HANDLE_RIGHT'
        edbone_right.bone_order = i

    bpy.ops.object.mode_set(mode='OBJECT')
    for i, p in enumerate(pos):
        bone = get_bone(armature.data.bones, group_id, 'CTRL', i)
        name = bone.name
        
        # adding constraints
        if i < len(pos):
            add_copy_location(armature, name, i, group_id)
        if i > 0:
            add_stretch_to(armature, name, i, group_id)
        if i == len(pos) - 1:
            next_ctrl_bone = get_bone(armature.data.bones, group_id, 'CTRL', i+1)
            add_stretch_to(armature, next_ctrl_bone.name, i+1, group_id)

        # setting handles
        add_handles(armature, i, group_id)
    # for the last control bone

    pose_bones = armature.pose.bones
    for pbone in pose_bones:
        rest_bone = pbone.bone
        if rest_bone.bone_type == 'CTRL':
            pbone.custom_shape = bpy.data.objects['ctrl_sphere']
            pbone.custom_shape_scale = 0.025
            rest_bone.layers[0] = True
            rest_bone.layers[-1] = False
            # TODO FIX this if bone has parent, hide it
            if pbone.parent:
                rest_bone.hide = True

        if rest_bone.bone_type.startswith('HANDLE'):
            pbone.custom_shape = bpy.data.objects['ctrl_cone']
            pbone.custom_shape_scale = 0.01
            rest_bone.show_wire = True
            rest_bone.layers[1] = True
            rest_bone.layers[0] = False
            rest_bone.layers[-1] = False


def add_armature(gp_ob, stroke, armature, group_id):
    """
    Adds an armature modifier to the greasepencil object
    Adds a new vertex group containing the stroke
    Sets the modifier to affect only that vertex group
    """
    
    name = armature.name + str(group_id)
    mod = gp_ob.grease_pencil_modifiers.new(type='GP_ARMATURE',
                                            name=name)

    mod.object = armature

    bpy.context.view_layer.objects.active = gp_ob
    bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
    bpy.ops.gpencil.select_all(action='DESELECT')

    for pt in stroke.points:
        pt.select = True

    con = change_context(gp_ob)
    vgroup = gp_ob.vertex_groups.new(name=name)
    vgroup.bone_group = group_id
    vgroup.deform_group = False
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
            vgroup = gp_ob.vertex_groups.new(name=b.name)
            vgroup.bone_group = bone_group
            vgroup.deform_group = True


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
        group for group in gp_ob.vertex_groups if group.deform_group and group.bone_group == bone_group]

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
    context.view_layer.objects.active = gp_ob
    # fit the curve
    error = error_threshold
    bpy.ops.gpencil.fit_curve(error_threshold=error,
                              target='ARMATURE',
                              stroke_index=stroke_index)

    pos, ease = get_bones_positions(context)
    # store the length of the chain for rigging purposes
    context.window_manager.gopo_prop_group.num_bones = len(pos)
    add_deform_bones(armature, pos, ease, group_id)
    add_control_bones(armature, pos, closed_threshold, group_id)
    add_armature(gp_ob, stroke, armature, group_id)
    add_vertex_groups(gp_ob, armature, group_id)
    add_weights(context, gp_ob, stroke, group_id)
    prepare_interface(armature)


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
        # Make sure the auxiliary objects have been created
        gp_auxiliary_objects.assure_auxiliary_objects(context)
        
        if context.mode == 'POSE':
            bpy.ops.object.mode_set(mode='OBJECT')
            
        gp_ob = context.window_manager.gopo_prop_group.gp_ob
        context.view_layer.objects.active = gp_ob
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


def register():
    bpy.utils.register_class(Gomez_OT_Poser)


def unregister():
    bpy.utils.unregister_class(Gomez_OT_Poser)
