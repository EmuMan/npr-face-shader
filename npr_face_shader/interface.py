import bpy

from . import functions

class ComputeFaceShadows(bpy.types.Operator):
    bl_idname = 'object.npr_shade_face'
    bl_label = 'NPR Shade Face'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        functions.create_face_shadow_map()
        return {'FINISHED'}

class FaceShadePanel(bpy.types.Panel):
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