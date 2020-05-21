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

bl_info = {
    "name": "Gomez Grease Pencil Poser",
    "description": "Automatic rigging of grease pencil strokes",
    "author": "dzigaVertov@github",
    "version": (0, 0, 1),
    "blender": (2,80,0),
    "location": "View3D",
    "warning": "This addon is still in development.",
    "wiki_url": "",
    "category": "Object"}


import bpy
from . import gp_armature_applier
from . import gomez_poser_ui


# register
##################################
def register():
    gp_armature_applier.register()
    gomez_poser_ui.register()

def unregister():
    gp_armature_applier.unregister()
    gomez_poser_ui.unregister()
