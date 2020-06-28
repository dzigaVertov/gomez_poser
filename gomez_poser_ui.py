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
        pbone.bone.rigged_stroke for pbone in pbones if pbone.bone.select)

    for pbone in pbones:

        ctrl_bone = pbone.name.startswith('ctrl')
        handle_bone = pbone.name.startswith('handle')

        if (ctrl_bone or handle_bone) and pbone.bone.rigged_stroke in ctrls_to_show:
            pbone.bone.layers[0] = True
            pbone.bone.layers[3] = True
        elif (ctrl_bone or handle_bone):
            pbone.bone.layers[0] = event.shift
            pbone.bone.layers[3] = True


        



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
    bpy.utils.register_class(GomezPTPanel)
    bpy.utils.register_class(GOMEZ_OT_go_draw)
    bpy.utils.register_class(GOMEZ_OT_go_pose)



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
    bpy.utils.unregister_class(GomezPTPanel)
    bpy.utils.unregister_class(GOMEZ_OT_go_draw)
    bpy.utils.unregister_class(GOMEZ_OT_go_pose)



    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


