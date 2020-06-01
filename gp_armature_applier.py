import bpy

from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.props import BoolProperty, PointerProperty, CollectionProperty, StringProperty
from mathutils import Vector, Matrix

def get_target_strokes(context):
    """
    Returns the bonegroups of the strokes where the modifier should be applied
    They correspond to the active layer and the active frame of the
    active object.
    (Returns the selected strokes for now)
    """
    gp_ob = context.object
    all_strokes = gp_ob.data.layers.active.active_frame.strokes

    return [stroke.bone_groups for stroke in all_strokes if stroke.select]

def clean_strokes(context, group_id):
    """
    Set all strokes from bonegroup group_id to no group
    """
    prop_group = context.window_manager.gopo_prop_group
    gp_ob = prop_group.gp_ob

    for layer in gp_ob.data.layers:
        for frame in layer.frames:
            for stroke in frame.strokes:
                if stroke.bone_groups == group_id:
                    stroke.bone_groups = 0

def clean_gp_object(context, group_id):
    """
    Remove all deform and armature vertex groups pertaining the group_id bone group.
    Remove the corresponding armature modifier.
    Remove the corresponding stroke
    """
    prop_group = context.window_manager.gopo_prop_group
    gp_ob = prop_group.gp_ob

    for vgroup in gp_ob.vertex_groups:
        if vgroup.name.startswith('Armature' + str(group_id)):
            for mod in gp_ob.grease_pencil_modifiers:
                if mod.vertex_group == vgroup.name:
                    gp_ob.grease_pencil_modifiers.remove(mod)
                    gp_ob.vertex_groups.remove(vgroup)
                    break
        elif vgroup.name.startswith('deform_' + str(group_id)):
            gp_ob.vertex_groups.remove(vgroup)

    for layer in gp_ob.data.layers:
        for frame in layer.frames:
            for stroke in frame.strokes:
                if stroke.bone_groups == group_id:
                    frame.strokes.remove(stroke)
                

def clean_bones(context,group_id):
    armature = context.window_manager.gopo_prop_group.ob_armature
    act_ob = context.object
    curr_mode = context.mode

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    context.view_layer.objects.active = armature
    armature.hide_viewport = False
    bpy.ops.object.mode_set(mode='EDIT')

    for edbone in armature.data.edit_bones:
        if edbone.rigged_stroke == group_id:
            armature.data.edit_bones.remove(edbone)

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    context.view_layer.objects.active = act_ob
    bpy.ops.object.mode_set(mode=curr_mode)
    
                    

class GOMEZ_OT_clean_baked(bpy.types.Operator):
    """
    Cleans vertex groups and bones from baked strokes
    """
    bl_idname = "greasepencil.gp_clean_baked"
    bl_label = "Clean baked stroke"
    bl_options = {'REGISTER', 'UNDO'}

    group_id : IntProperty(name='bgroup', default=1)

    def invoke(self, context, event):
        if context.mode == 'POSE' and context.active_pose_bone:
            self.group_id = context.active_pose_bone.rigged_stroke
        elif context.mode == 'EDIT_GPENCIL':
            for stroke in context.object.data.layers.active.active_frame.strokes:
                if stroke.select:
                    self.group_id = stroke.bone_groups
        return self.execute(context)

    def execute(self, context):
        if not self.group_id:
            return {'CANCELLED'}

        # clean_strokes(context, self.group_id)
        clean_gp_object(context, self.group_id)
        clean_bones(context, self.group_id)

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return context.mode in {'POSE', 'EDIT_GPENCIL'}


    
    
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
    bake_to_new_layer : BoolProperty(name='bake_to_new_layer', description='Bake the stroke to new layer', default=False)

    def bake_stroke(self, context, gp_ob, gp_obeval, new_layer, group_id):
        inf = self.frame_init
        outf = self.frame_end
        step = self.step

        for idx,stroke in enumerate(gp_ob.data.layers.active.active_frame.strokes):
            if stroke.bone_groups == group_id:
                stroke_idx = idx

        for fr in range(inf, outf+1, step):
            context.scene.frame_set(fr)

            # TODO: See to take this out of the loop
            evald_stroke = gp_obeval.data.layers.active.active_frame.strokes[stroke_idx]
            n_points = len(evald_stroke.points)

            if new_layer.active_frame and new_layer.active_frame.frame_number == fr:
                frame = new_layer.active_frame
            else:
                frame = new_layer.frames.new(fr, active=True)
                
            stroke = frame.strokes.new()
            stroke.points.add(n_points)
            stroke.line_width = evald_stroke.line_width
            stroke.material_index = evald_stroke.material_index

            pts_eval = ((pt.co.copy(), pt.strength, pt.pressure, pt.vertex_color) for pt in evald_stroke.points)

            # TODO: Change this to for_each_set
            for gp_pt, pt in zip(stroke.points, pts_eval):
                coords, strength, pressure, v_color = pt
                gp_pt.co = coords
                gp_pt.strength = strength
                gp_pt.pressure = pressure
                gp_pt.vertex_color = v_color
                

    def invoke(self, context, event):
        props = context.window_manager.gopo_prop_group
        self.frame_init = props.frame_init
        self.frame_end =  props.frame_end
        self.step = props.bake_step
        self.bake_to_new_layer = props.bake_to_new_layer

        return self.execute(context)


    def execute(self, context):        
        
        bone_groups = get_target_strokes(context)
        depsgraph = context.evaluated_depsgraph_get()
        gp_ob = context.object
        gp_obeval = gp_ob.evaluated_get(depsgraph)
        layer_to_bake = gp_ob.data.layers.active

        if self.bake_to_new_layer:
            layer = gp_ob.data.layers.new('baked_' + layer_to_bake.info , set_active=False)
        else:
            layer = gp_ob.data.layers.active 

        for group_id in bone_groups:
            self.bake_stroke(context, gp_ob, gp_obeval,layer, group_id)
            bpy.ops.greasepencil.gp_clean_baked(group_id=group_id)

        return {'FINISHED'}


    @classmethod
    def poll(cls, context):
        """
        There must be an active greasepencil object with active layer and active frame
        """
        
        if context.object:
            if context.object.type == 'GPENCIL':
                if context.object.data.layers.active:
                    if context.object.data.layers.active.active_frame:
                        return True

        return False
        
class GOMEZ_OT_clean_strokes(bpy.types.Operator):
    bl_idname = 'greasepencil.clean_stroke'
    bl_label = 'Remove vertex group, armature modifier and bones'
    bl_options = {'REGISTER', 'UNDO'}

    stroke_indices : bpy.props.IntVectorProperty(name='indices of strokes',
                                                 description='strokes to be cleaned',
                                                 default=(-1))

    def execute(self, context):
        gp_ob = context.object
        for idx in self.stroke_indices:
            pass
        
            

class GOMEZ_OT_select_all_stroke_ctrls(bpy.types.Operator):
    bl_idname = 'armature.select_all_ctrls'
    bl_label = 'Select all controls of a given stroke'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.object
        indices = [bone.rigged_stroke for bone in armature.data.bones if bone.select]

        for bone in armature.data.bones:
            if bone.name.startswith('ctrl') and bone.rigged_stroke in indices:
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

def unregister():
    bpy.utils.unregister_class(GOMEZ_OT_bake_animation)
    bpy.utils.unregister_class(GOMEZ_OT_clean_baked)
    bpy.utils.unregister_class(GOMEZ_OT_select_all_stroke_ctrls)

        
    
