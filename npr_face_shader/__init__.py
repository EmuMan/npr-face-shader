# -*- coding: utf-8 -*-

bl_info = {
    "name": "NPR Face Shader",
    "author": "EmuMan",
    "version": (0, 1, 2),
    "blender": (3, 6, 1),
    "location": "View3D > Sidebar > Face Shader Panel",
    "description": "A utility for easily generating smooth face shading on characters via grease pencil without using normal editing or external programs.",
    "warning": "",
    # "doc_url": "https://mmd-blender.fandom.com/wiki/MMD_Tools",
    # "wiki_url": "https://mmd-blender.fandom.com/wiki/MMD_Tools",
    # "tracker_url": "https://github.com/UuuNyaa/blender_mmd_tools/issues",
    "category": "Object",
}

# This block is needed to play nicely with multiprocessing
try:
    import bpy
    from .interface import *

    classes = [
        FaceShadeProps,
        ComputeFaceShadows,
        CreateMaterialOnly,
        CreateNodeGroupOnly,
        FaceShadePanel,
    ]
except ImportError:
    pass


def register():
    for bpy_class in classes:
        bpy.utils.register_class(bpy_class)
    bpy.types.Object.face_shade_props = bpy.props.PointerProperty(type=FaceShadeProps)

def unregister():
    try:
        del bpy.types.Object.face_shade_props
    except AttributeError:
        pass
    for bpy_class in classes:
        bpy.utils.unregister_class(bpy_class)

if __name__ == "__main__":
    register()
