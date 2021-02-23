import bpy
from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.props import BoolProperty, PointerProperty, CollectionProperty, StringProperty
from mathutils import Vector, Matrix

def can_remove_vg(gp_ob, vgroup):
    """
    Check if there are still strokes assigned to this vertex_group
    """
    # TODO: this can be easily optimized
    for layer in gp_ob.data.layers:
        for frame in layer.frames:
            for stroke in frame.strokes:
                for group in stroke.groups:
                    if group.group == vgroup.index:
                        return False
    return True


def remove_vertex_groups(gp_ob, group_id, remove_bonegroup=False, is_resampling=False):
    """
    Removes vertex groups from a a grease pencil object pertaining
    a bonegroup.
    Removes only deform_groups if we are not removing a bonegroup completely
    (could be resampling)
    """
    for vgroup in gp_ob.vertex_groups:
        if vgroup.bone_group == group_id:
            if remove_bonegroup:
                gp_ob.vertex_groups.remove(vgroup)
            elif is_resampling and vgroup.deform_group:
                gp_ob.vertex_groups.remove(vgroup)

            
def get_def_vgroup(gp_ob, group_id):
    """
    Return the vertex group corresponding to the group_id 
    (The vertex group that the armature modifier is applied to)
    """
    for mod in gp_ob.grease_pencil_modifiers:
        vgroup = gp_ob.vertex_groups[mod.vertex_group]

        if vgroup.bone_group and vgroup.bone_group == group_id:
            return vgroup

            
def are_we_removing_bonegroup(context, group_id):
    """
    Check if there are still strokes affected by this modifier
    """
    prop_group = context.window_manager.gopo_prop_group
    gp_ob = prop_group.gp_ob
    vgroup = get_def_vgroup(gp_ob, group_id)

    if not vgroup:
        return False
    
    for layer in gp_ob.data.layers:
        for frame in layer.frames:
            for stroke in frame.strokes:
                try:
                    weight = stroke.points.weight_get(
                        vertex_group_index=vgroup.index, point_index=0)
                    if weight < 0: # Apparently a bug in the python API
                        continue
                    else:
                        return False
                except RuntimeError:
                    continue
    return True


def remove_armature_mod(gp_ob, group_id):
    """
    Remove armature modifier from a grease pencil object, pertaining
    a bonegroup if it doesn't affect more strokes.
    Returns True if it removes the modifier
    """
    for mod in gp_ob.grease_pencil_modifiers:
        vgroup = gp_ob.vertex_groups[mod.vertex_group]

        if vgroup.bone_group and vgroup.bone_group == group_id:
            gp_ob.grease_pencil_modifiers.remove(mod)
            return True


def remove_stroke(gp_ob, group_id):
    """
    Removes a stroke with a given bonegroup
    """
    for layer in gp_ob.data.layers:
        for frame in layer.frames:
            for stroke in frame.strokes:
                if stroke.bone_groups == group_id:
                    frame.strokes.remove(stroke)
    

def get_target_strokes(context):
    """
    Returns the bonegroups of the strokes where the modifier should be applied
    They correspond to the active frame of all the layers of the
    active object.
    (Returns the selected strokes for now)
    """
    gp_ob = context.object
    all_strokes = [stroke for layer in gp_ob.data.layers if not layer.lock for stroke in layer.strokes]

    return set([stroke.bone_groups for stroke in all_strokes if stroke.select])


def clean_strokes(context, group_id, init_frame, end_frame, layer_name='ALL'):
    """
    For all keyframes in gp_ob, between init_frame and end_frame, and all strokes
    in those keyframes belonging to group_id, remove all weights from the points.  
    """
    prop_group = context.window_manager.gopo_prop_group
    gp_ob = prop_group.gp_ob

    layers = gp_ob.data.layers if layer_name=='ALL' else [gp_ob.data.layers[layer_name]]
    for layer in layers:
        for frame in layer.frames:
            # TODO: check the case of active frame with frame_number < init_frame
            f_number = frame.frame_number
            if f_number < init_frame or f_number > end_frame:
                continue
            bpy.ops.gpencil.clean_keyframe(bone_group=group_id,
                                           frame_number=f_number,
                                           layer_name=layer.info)
            for stroke in frame.strokes:
                if stroke.bone_groups == group_id:
                    stroke.bone_groups = 0

                    
def clean_gp_object(context, group_id, init_frame, end_frame, remove_bonegroup):
    """
    Remove all deform and armature vertex groups pertaining the group_id bone group if there are no more strokes being affected.
    
    Remove the corresponding armature modifier if there are no more strokes being affected.
    
    """
    prop_group = context.window_manager.gopo_prop_group
    gp_ob = prop_group.gp_ob

    if remove_bonegroup:
        remove_armature_mod(gp_ob, group_id)
    
    remove_vertex_groups(gp_ob, group_id, remove_bonegroup=remove_bonegroup)

    


def clean_animation_data(context, action_groups):
    """
    Remove the action_groups from the active action in the armature
    once the corresponding bones have been deleted.
    """
    armature = context.window_manager.gopo_prop_group.ob_armature
    action = armature.animation_data.action

    if not action:
        return
    
    curves_to_remove = []
    for curve in action.fcurves:
        if curve.group.name in action_groups:
            curves_to_remove.append(curve)

    for curve in curves_to_remove:
        action.fcurves.remove(curve)

    
def clean_bones(context,group_id):
    """
    Remove bones from baked stroke
    """
    armature = context.window_manager.gopo_prop_group.ob_armature
    act_ob = context.object
    curr_mode = context.mode

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    context.view_layer.objects.active = armature
    armature.hide_viewport = False
    bpy.ops.object.mode_set(mode='EDIT')

    # Use this to remove the action groups
    groups_names = []
    for edbone in armature.data.edit_bones:
        if edbone.rigged_stroke == group_id:
            groups_names.append(edbone.name)
            armature.data.edit_bones.remove(edbone)
            

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    context.view_layer.objects.active = act_ob
    bpy.ops.object.mode_set(mode=curr_mode)
    return groups_names
    
                    

class GOMEZ_OT_clean_baked(bpy.types.Operator):
    """
    Cleans vertex groups and bones from baked strokes
    """
    bl_idname = "greasepencil.gp_clean_baked"
    bl_label = "Clean baked stroke"
    bl_options = {'REGISTER', 'UNDO'}

    group_id : IntProperty(name='bgroup', default=1)
    init_frame : IntProperty(name='init_frame', default=1)
    end_frame : IntProperty(name= 'end_frame', default=1)
    layer_name : StringProperty(name='layer_name',
                                description='The name of the layer to clean',
                                default='',
                                maxlen=64)

    def invoke(self, context, event):
        if context.mode == 'POSE' and context.active_pose_bone:
            self.group_id = context.active_pose_bone.rigged_stroke
        elif context.mode == 'EDIT_GPENCIL':
            if self.layer_name == '':
                layer = context.object.data.layers.active
            else:
                layer = context.object.data.layers[self.layer_name]
            for stroke in layer.active_frame.strokes:
                if stroke.select:
                    self.group_id = stroke.bone_groups
        return self.execute(context)

    
    def execute(self, context):
        if not (self.group_id and self.init_frame and self.end_frame):
            return {'CANCELLED'}

        if self.layer_name == '':
            layer_name = context.object.data.layers.active.info
        else:
            layer_name = self.layer_name
                
        clean_strokes(context,
                      self.group_id,
                      self.init_frame,
                      self.end_frame,
                      layer_name=layer_name)

        remove_bone_group = are_we_removing_bonegroup(context, self.group_id)
        
        clean_gp_object(context,
                        self.group_id,
                        self.init_frame,
                        self.end_frame,
                        remove_bone_group)
        if remove_bone_group:
            action_groups = clean_bones(context, self.group_id)
            clean_animation_data(context, action_groups)
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return context.mode in {'POSE', 'EDIT_GPENCIL', 'OBJECT'}


    
    
class GOMEZ_OT_bake_animation(bpy.types.Operator):
    """
    Bake a gpencil-armature modifier animation for a range of frames.
    It bakes the data to the same layer or to a new layer
    """
    bl_idname = "greasepencil.gp_bake_animation"
    bl_label = "Bake to keys"
    bl_options = {'REGISTER', 'UNDO'}

    frame_init : IntProperty(name='start frame',
                             description="the frame to start applying the modifier",
                             default=1, min=0, max=1000000)

    frame_end : IntProperty(name='end frame',
                             description="the frame to stop applying the modifier",
                             default=1, min=0, max=1000000)

    step : IntProperty(name='frame_step',
                       description='step between baked steps',
                       default=1,
                       min=1,
                       max=1000000)

    bake_to_new_layer : BoolProperty(name='bake_to_new_layer',
                                     description='Bake the stroke to new layer',
                                     default=False)


    split : BoolProperty(name='split',
                         description='Split the stroke between a baked and a rigged part',
                         default=False)
    
    
    
    def bake_stroke(self, context, gp_ob, gp_obeval, source_layer, target_layer, group_id):
        inf = self.frame_init
        outf = self.frame_end
        step = self.step
        
        stroke = None
        for idx,st in enumerate(source_layer.active_frame.strokes):
            if st.bone_groups == group_id:
                stroke_idx = idx
                stroke = st

        if not stroke:
            return         

        material_index = stroke.material_index
        line_width = stroke.line_width
        vertex_color_fill = stroke.vertex_color_fill
        # First get the points.
        baked_points = dict()
        
        for fr in range(inf, outf+1, step):
            context.scene.frame_set(fr)

            evald_stroke = gp_obeval.data.layers[source_layer.info].active_frame.strokes[stroke_idx]

            pts_eval = list((pt.co.copy(), pt.strength, pt.pressure, pt.vertex_color) for pt in evald_stroke.points)

            baked_points[fr] = pts_eval

        # now create frames and strokes
        for fr in range(inf, outf+1, step):
            context.scene.frame_set(fr)
            
            n_points = len(stroke.points)

            if target_layer.active_frame and target_layer.active_frame.frame_number == fr:
                frame = target_layer.active_frame
            else:
                frame = target_layer.frames.new(fr, active=True)
                
            new_stroke = frame.strokes.new()
            new_stroke.points.add(n_points)
            new_stroke.line_width = line_width
            new_stroke.material_index = material_index
            new_stroke.vertex_color_fill = vertex_color_fill
            
            # TODO: Change this to for_each_set
            for gp_pt, pt in zip(new_stroke.points, baked_points[fr]):
                coords, strength, pressure, v_color = pt
                gp_pt.co = coords
                gp_pt.strength = strength
                gp_pt.pressure = pressure
                gp_pt.vertex_color = v_color
                

    def invoke(self, context, event):
        props = context.window_manager.gopo_prop_group

        if props.bake_from_active_to_current:
            gp_ob = props.gp_ob
            self.frame_init = gp_ob.data.layers.active.active_frame.frame_number
            self.frame_end = context.scene.frame_current
        else:
            self.frame_init = props.frame_init
            self.frame_end =  props.frame_end
        self.step = props.bake_step
        self.bake_to_new_layer = props.bake_to_new_layer

        return self.execute(context)


    def execute(self, context):
        if context.mode =='POSE':
            bone_groups = set()
            for pbone in context.selected_pose_bones:
                bone_groups.add(pbone.bone.rigged_stroke)
            bpy.ops.object.mode_set(mode='OBJECT')
            gp_ob = context.window_manager.gopo_prop_group.gp_ob
            gp_ob.select_set(True)
            context.view_layer.objects.active = gp_ob
        else:
            bone_groups = get_target_strokes(context)
        gp_ob = context.object
        depsgraph = context.evaluated_depsgraph_get()
        gp_obeval = gp_ob.evaluated_get(depsgraph)

        layers = [layer for layer in gp_ob.data.layers if not layer.lock]
        for layer in layers:
            gp_ob.data.layers.active = layer 
            kf_frame_number = layer.active_frame.frame_number

            if kf_frame_number < self.frame_init:
                self.split = True
        
            if self.bake_to_new_layer:
                new_layer = gp_ob.data.layers.new('baked_' + layer.info , set_active=False)
            else:
                new_layer = gp_ob.data.layers.active 

            for group_id in bone_groups:
                self.bake_stroke(context, gp_ob, gp_obeval,layer, new_layer,  group_id)

        for layer in layers:
            for group_id in bone_groups:
                bpy.ops.greasepencil.gp_clean_baked(group_id=group_id,
                                                    init_frame=self.frame_init,
                                                    end_frame=self.frame_end,
                                                    layer_name = layer.info)

        return {'FINISHED'}


    @classmethod
    def poll(cls, context):
        """
        There must be an active greasepencil object with active layer and active frame
        Or we must be posing the armature
        """
        if context.mode == 'POSE':
            if context.active_pose_bone:
                return True
        if context.object:
            if context.object.type == 'GPENCIL':
                if context.object.data.layers.active:
                    if context.object.data.layers.active.active_frame:
                        return True

        return False


    
class GOMEZ_OT_select_all_stroke_ctrls(bpy.types.Operator):
    bl_idname = 'armature.select_all_ctrls'
    bl_label = 'Select all controls of a given stroke'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.object
        indices = [bone.rigged_stroke for bone in armature.data.bones if bone.select]

        for bone in armature.data.bones:
            if bone.poser_control and bone.rigged_stroke in indices:
                bone.select = True
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        armature = context.window_manager.gopo_prop_group.ob_armature
        return armature and context.mode == 'POSE' 
        

class GOMEZ_OT_select_bonegroup(bpy.types.Operator):
    bl_idname = 'armature.select_bonegroup'
    bl_label = 'Select all bones of a given stroke'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.object
        indices = [bone.rigged_stroke for bone in armature.data.bones if bone.select]

        for bone in armature.data.bones:
            poser_bone = any(bone.poser_control,
                             bone.poser_handle,
                             bone.poser_root,
                             bone.poser_deform)
            
            if poser_bone and bone.rigged_stroke in indices:
                bone.select = True
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        armature = context.window_manager.gopo_prop_group.ob_armature
        return armature and context.mode == 'POSE' 
        
        

        

            
def register():
    bpy.utils.register_class(GOMEZ_OT_bake_animation)
    bpy.utils.register_class(GOMEZ_OT_clean_baked)
    bpy.utils.register_class(GOMEZ_OT_select_all_stroke_ctrls)
    bpy.utils.register_class(GOMEZ_OT_select_bonegroup)

def unregister():
    bpy.utils.unregister_class(GOMEZ_OT_bake_animation)
    bpy.utils.unregister_class(GOMEZ_OT_clean_baked)
    bpy.utils.unregister_class(GOMEZ_OT_select_all_stroke_ctrls)
    bpy.utils.unregister_class(GOMEZ_OT_select_bonegroup)

        
    
