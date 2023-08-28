# -*- coding: utf-8 -*-

bl_info = {
    "name": "NPR Face Shader",
    "author": "EmuMan",
    "version": (0, 1, 0),
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
from . import utils

class ComputeFaceShadows(bpy.types.Operator):
    bl_idname = 'object.npr_shade_face'
    bl_label = 'NPR Shade Face'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        utils.main()
        return {'FINISHED'}

class FACE_SHADE_PT_Panel(bpy.types.Panel):
    bl_idname = 'FACE_SHADE_PT_Panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Face Shader'
    bl_label = 'NPR Face Shader'

    def draw(self, context):
        self.layout.operator(
            operator=ComputeFaceShadows.bl_idname,
            text='Generate Face Shading'
        )

def register():
    bpy.utils.register_class(ComputeFaceShadows)
    bpy.utils.register_class(FACE_SHADE_PT_Panel)
    print('register')

def unregister():
    bpy.utils.unregister_class(ComputeFaceShadows)
    bpy.utils.unregister_class(FACE_SHADE_PT_Panel)
    print('unregister')

if __name__ == "__main__":
    register()
