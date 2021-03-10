import bpy
from bpy.props import IntProperty

def create_new_gp_object(context):
    """
    Creates a new grease pencil object and links it to the scene
    """
    name = 'baked' + context.active_object.name
    gp_data_new = bpy.data.grease_pencils.new(name)
    gp_ob_new = bpy.data.objects.new(name, gp_data_new)
    bpy.data.materials.create_gpencil_data(bpy.data.materials.new(name))
    gp_ob_new.data.materials.append(bpy.data.materials[name])
    context.scene.collection.objects.link(gp_ob_new)
    gp_data_new.layers.new(name)
    return gp_ob_new

def bake_curve(context, curve, new_gp, frame_init, frame_end):
    """
    Bakes an animated curve to the grease pencil object.
    """
    # 0) Crear una curva temporaria para guardar cada una de las curvas intermedias.
    # Para cada frame:
    # 1) Generar el depsgraph actualizado.
    # 2) Obtener el objeto evaluado de la curva.
    # 3) Guardar la curva anterior
    # 4) Obtener la curva del objeto evaluado con new_from_object
    # 5) Guardarla en temp.
    # 6) Convertir a objeto Grease pencil.
    # 7) Copiar el keyframe al new_gp
    # 8) Setear el frame number
    # 9) Borrar el objeto Grease Pencil.
    # 10) Borrar la curva anterior.

    temp_data = bpy.data.curves.new('temp_data', 'CURVE')
    temp_curve_object = bpy.data.objects.new('temp_curve_object', temp_data)
    context.scene.collection.objects.link(temp_curve_object)
    bpy.ops.object.select_all(action='DESELECT')

    for fr in range(frame_init, frame_end + 1):
        context.view_layer.objects.active = temp_curve_object
        temp_curve_object.select_set(True)
        context.scene.frame_set(fr)
        dg = context.evaluated_depsgraph_get()
        evald_curve = curve.evaluated_get(dg)
        prev_data = temp_curve_object.data
        evald_data = bpy.data.curves.new_from_object(evald_curve,
                                                     preserve_all_data_layers=True,
                                                     depsgraph=dg)
        temp_curve_object.data = evald_data
        bpy.ops.object.convert(target='GPENCIL', keep_original=True, thickness=100)
        frame = context.object.data.layers.active.active_frame
        new_frame = new_gp.data.layers.active.frames.copy(frame)
        new_frame.frame_number = fr
        bpy.data.objects.remove(context.object)
        bpy.data.curves.remove(prev_data)
    bpy.data.objects.remove(temp_curve_object)
        
        
        
        
    


class GOMEZ_OT_bake_curve(bpy.types.Operator):
    """
    Bakes an animated curve to a Grease Pencil object.
    """
    bl_idname = "curve.gp_bake_curve"
    bl_label = "Bake curve to Grease Pencil"
    bl_options = {'REGISTER', 'UNDO'}

    frame_init : IntProperty(name='init_frame', default = 1)
    frame_end : IntProperty(name='end_frame', default=1)

    def invoke(self, context, event):
        props = context.window_manager.gopo_prop_group
        self.frame_init = props.frame_init
        self.frame_end = props.frame_end
        return self.execute(context)

    def execute(self, context):
        curve = context.active_object
        new_gp = create_new_gp_object(context)
        bake_curve(context, curve, new_gp, self.frame_init, self.frame_end)
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        if context.active_object and context.active_object.type == 'CURVE':
            return True
        return False

def register():
    bpy.utils.register_class(GOMEZ_OT_bake_curve)

def unregister():
    bpy.utils.unregister_class(GOMEZ_OT_bake_curve)

        

