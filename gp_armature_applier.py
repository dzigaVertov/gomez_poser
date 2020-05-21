import bpy

from bpy.props import FloatProperty
from bpy.props import IntProperty
from bpy.props import BoolProperty, PointerProperty, CollectionProperty, StringProperty
from mathutils import Vector, Matrix

def get_target_strokes(context):
    """
    Returns the strokes where the modifier should be applied
    They correspond to the active layer and the active frame of the
    active object.
    (Returns the selected strokes for now)
    """
    gp_ob = context.object
    all_strokes = gp_ob.data.layers.active.active_frame.strokes

    return [idx for idx,stroke in enumerate(all_strokes) if stroke.select]


class GOMEZ_OT_bake_animation(bpy.types.Operator):
    """
    Bake a gpencil-armature modifier animation for a range of frames.
    It bakes the data to the same layer or to a new layer
    """
    bl_idname = "greasepencil.gp_bake_animation"
    bl_label = "Gposer op"
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

    def bake_stroke(self, context, gp_ob, gp_obeval, new_layer, stroke_idx):
        inf = self.frame_init
        outf = self.frame_end
        step = self.step

        for fr in range(inf, outf+1, step):
            context.scene.frame_set(fr)

            evald_stroke = gp_obeval.data.layers.active.active_frame.strokes[stroke_idx]
            n_points = len(evald_stroke.points)

            if new_layer.active_frame and new_layer.active_frame.frame_number == fr:
                frame = new_layer.active_frame
            else:
                frame = new_layer.frames.new(fr, active=True)
                
            stroke = frame.strokes.new()
            stroke.points.add(n_points)
            stroke.line_width = evald_stroke.line_width

            pts_eval = ((pt.co.copy(), pt.strength, pt.pressure) for pt in evald_stroke.points)

            # TODO: Change this to for_each_set
            for gp_pt, pt in zip(stroke.points, pts_eval):
                coords, strength, pressure = pt
                gp_pt.co = coords
                gp_pt.strength = strength
                gp_pt.pressure = pressure
                

    def invoke(self, context, event):
        self.frame_init = context.window_manager.gopo_prop_group.frame_init
        self.frame_end =  context.window_manager.gopo_prop_group.frame_end
        self.step = context.window_manager.gopo_prop_group.bake_step

        return self.execute(context)


    def execute(self, context):        
        
        strokes = get_target_strokes(context)
        depsgraph = context.evaluated_depsgraph_get()
        gp_ob = context.object
        gp_obeval = gp_ob.evaluated_get(depsgraph)
        layer_to_bake = gp_ob.data.layers.active

        new_layer = gp_ob.data.layers.new('baked_' + layer_to_bake.info , set_active=False)
        for stroke_idx in strokes:
            self.bake_stroke(context, gp_ob, gp_obeval,new_layer, stroke_idx)

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
        
class GOMEZ_OT_clean_stroke(bpy.types.Operator):
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
        
            
            

        

            
def register():
    bpy.utils.register_class(GOMEZ_OT_bake_animation)

def unregister():
    bpy.utils.unregister_class(GOMEZ_OT_bake_animation)


        
    
