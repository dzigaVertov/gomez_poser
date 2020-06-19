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
from bpy.props import FloatProperty, IntProperty, FloatVectorProperty, BoolProperty, PointerProperty, CollectionProperty, StringProperty
from math import log
from .gp_armature_applier import remove_vertex_groups
from .gp_rigging_ops import add_vertex_groups, add_weights


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
        

def register():
    bpy.utils.register_class(GOMEZ_OT_resample_rigged)
    

def unregister():
    bpy.utils.unregister_class(GOMEZ_OT_resample_rigged)
    

    
