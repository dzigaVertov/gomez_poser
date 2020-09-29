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

    bake_to_new_layer: BoolProperty(name='bake_to_new_layer',
                                    description='Bake the stroke to new layer',
                                    default=False)

    bake_from_active_to_current: BoolProperty(name='from_active_to_current',
                                              description='Bake stroke from active keyframe to current frame',
                                              default=True)


def register():
    bpy.utils.register_class(FittedBone)
    bpy.utils.register_class(GopoProperties)

    
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

    bpy.types.Bone.bone_order = IntProperty(name='bone_order',
                                            description='Place that the bone occupies in a chain, starting from 0',
                                            default=-1)
    bpy.types.EditBone.bone_order = IntProperty(name='bone_order',
                                            description='Place that the bone occupies in a chain, starting from 0',
                                            default=-1)

    bpy.types.GreasePencil.current_bone_group = IntProperty(default=0)

def unregister():
    bpy.utils.unregister_class(FittedBone)
    bpy.utils.unregister_class(GopoProperties)

    del bpy.types.WindowManager.gopo_prop_group
    del bpy.types.WindowManager.fitted_bones
    del bpy.types.Bone.rigged_stroke
    del bpy.types.EditBone.rigged_stroke
    del bpy.types.Bone.bone_order
    del bpy.types.EditBone.bone_order
    del bpy.types.GreasePencil.current_bone_group
