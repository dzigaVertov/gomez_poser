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
import bmesh


def add_auxiliary_meshes(context):
    """
    Crear objetos para reemplazar la apariencia de ctrl bones
    """
    
    # Crear collection para guardar meshes auxiliares
    aux_col = bpy.data.collections.new('auxiliary_meshes')
    context.scene.collection.children.link(aux_col)
    aux_col.hide_viewport = True
    aux_col.hide_render = True

    # ESFERA
    # Crear objeto y mesh vacíos
    control_sphere_mesh = bpy.data.meshes.new('ctrl_sphere')
    ctrl_sphere_ob = bpy.data.objects.new('ctrl_sphere', control_sphere_mesh)
    # Linkear objeto a collection, hacer activo
    aux_col.objects.link(ctrl_sphere_ob)
    ctrl_sphere_ob.select_set(True)
    context.view_layer.objects.active = ctrl_sphere_ob

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
    context.view_layer.objects.active = ctrl_cone_ob

    # Crear geometría
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=True,
                          segments=8, diameter1=0.25, depth=0.25)
    bm.to_mesh(control_cone_mesh)
    bm.free()

    ctrl_cone_ob.display_type = 'WIRE'
    


def assure_auxiliary_objects(context):
    initialized = context.window_manager.gopo_prop_group.initialized
    if initialized:
        return

    add_auxiliary_meshes(context)
    context.window_manager.gopo_prop_group.initialized = True
