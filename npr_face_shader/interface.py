import bpy

from multiprocessing.pool import Pool

from . import functions

class FaceShadeProps(bpy.types.PropertyGroup):

    target: bpy.props.PointerProperty(name='Target Object', type=bpy.types.Object)
    vertical_lines: bpy.props.PointerProperty(name='Vertical Lines', type=bpy.types.Object)
    shadow_shapes: bpy.props.PointerProperty(name='Shadow Shapes', type=bpy.types.Object)
    highlight_shapes: bpy.props.PointerProperty(name='Highlight Shapes', type=bpy.types.Object)
    output_image: bpy.props.PointerProperty(name='Output Image', type=bpy.types.Image)
    blur_size: bpy.props.IntProperty(name='Blur Size', default=25, min=1)

class ComputeFaceShadows(bpy.types.Operator):
    bl_idname = 'object.npr_shade_face'
    bl_label = 'NPR Shade Face'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.mode == 'OBJECT'

    def execute(self, context):
        with Pool(processes=8) as pool:
            functions.create_face_shadow_map(self, pool)
        return {'FINISHED'}

class FaceShadePanel(bpy.types.Panel):
    bl_idname = 'FACE_SHADE_PT_Panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Face Shader'
    bl_label = 'NPR Face Shader'

    def draw(self, context):
        props = bpy.data.objects[0].face_shade_props
        layout = self.layout

        col = layout.column(align=True)
        col.row(align=True).prop(props, 'target', text='Target Object')
        col.row(align=True).prop(props, 'vertical_lines', text='Vertical Lines')
        col.row(align=True).prop(props, 'shadow_shapes', text='Shadow Shapes')
        col.row(align=True).prop(props, 'highlight_shapes', text='Highlight Shapes')
        col.row(align=True).prop(props, 'output_image', text='Output Image')
        col.row(align=True).prop(props, 'blur_size', text='Blur Size')

        col.row(align=True).operator(
            operator=ComputeFaceShadows.bl_idname,
            text='Generate Face Shading'
        )
