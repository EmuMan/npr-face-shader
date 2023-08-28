# -*- coding: utf-8 -*-

bl_info = {
    "name": "NPR Face Shader",
    "author": "EmuMan",
    "version": (0, 1, 1),
    "blender": (3, 6, 1),
    "location": "View3D > Sidebar > Face Shader Panel",
    "description": "A utility for easily generating smooth face shading on characters via grease pencil without using normal editing or external programs.",
    "warning": "",
    # "doc_url": "https://mmd-blender.fandom.com/wiki/MMD_Tools",
    # "wiki_url": "https://mmd-blender.fandom.com/wiki/MMD_Tools",
    # "tracker_url": "https://github.com/UuuNyaa/blender_mmd_tools/issues",
    "category": "Object",
}

import bpy
from .interface import *

classes = [
    ComputeFaceShadows,
    FaceShadePanel,
]

def register():
    for bpy_class in classes:
        bpy.utils.register_class(bpy_class)

def unregister():
    for bpy_class in classes:
        bpy.utils.unregister_class(bpy_class)

if __name__ == "__main__":
    register()
