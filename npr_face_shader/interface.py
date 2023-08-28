import bpy

from multiprocessing.pool import Pool

from . import functions

class ComputeFaceShadows(bpy.types.Operator):
    bl_idname = 'object.npr_shade_face'
    bl_label = 'NPR Shade Face'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        with Pool(processes=8) as pool:
            functions.create_face_shadow_map(pool)
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