import bpy

from multiprocessing.pool import Pool
import json
import os

from . import functions
from . import nodes


NODE_GROUP_NAME = 'NPR Face Shadows'
NODE_GROUP_FILE = 'data/face_shadows_node_group.json'
DEFAULT_MATERIAL_NAME = 'NPR Face Shader'


def get_absolute_path(relative_path: str) -> str:
    return os.path.join(os.path.dirname(__file__), relative_path)

class FaceShadeProps(bpy.types.PropertyGroup):

    target: bpy.props.PointerProperty(name='Target Object', type=bpy.types.Object)
    vertical_lines: bpy.props.PointerProperty(name='Vertical Lines', type=bpy.types.Object)
    shadow_shapes: bpy.props.PointerProperty(name='Shadow Shapes', type=bpy.types.Object)
    highlight_shapes: bpy.props.PointerProperty(name='Highlight Shapes', type=bpy.types.Object)
    output_image: bpy.props.PointerProperty(name='Output Image', type=bpy.types.Image)
    blur_size: bpy.props.IntProperty(name='Blur Size', default=25, min=1)
    material_name: bpy.props.StringProperty(name='Material Name', default=DEFAULT_MATERIAL_NAME)
    uv_map_name: bpy.props.StringProperty(name='UV Map Name')
    sun_driver: bpy.props.PointerProperty(name='Sun Driver Target', type=bpy.types.Object)
    head_driver: bpy.props.PointerProperty(name='Head Driver Target', type=bpy.types.Object)

class ComputeFaceShadows(bpy.types.Operator):
    bl_idname = 'object.npr_shade_face'
    bl_label = 'NPR Shade Face'
    bl_description = 'Use the specified lines and parameters to generate a custom face shadow image.'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.mode == 'OBJECT'

    def execute(self, context):
        with Pool(processes=8) as pool:
            functions.create_face_shadow_map(self, pool)
        bpy.ops.object.npr_shade_face_create_material()
        props: FaceShadeProps = bpy.data.objects[0].face_shade_props
        props.target.active_material = bpy.data.materials[props.material_name]
        return {'FINISHED'}

class CreateMaterialOnly(bpy.types.Operator):
    bl_idname = 'object.npr_shade_face_create_material'
    bl_label = 'NPR Shade Face Create Material Only'
    bl_description = 'Create a new material set up with the required face shading node structure.'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        props: FaceShadeProps = bpy.data.objects[0].face_shade_props

        if props.target == None:
            uv_map = props.uv_map_name
        elif props.uv_map_name == '':
            uv_map = props.target.data.uv_layers.active.name
        else:
            try:
                uv_map = props.target.data.uv_layers[props.uv_map_name].name
            except KeyError:
                self.report({'ERROR'}, 'Invalid UV map name for target mesh.')

        if NODE_GROUP_NAME in bpy.data.node_groups:
            node_group = bpy.data.node_groups[NODE_GROUP_NAME]
        else:
            with open(get_absolute_path(NODE_GROUP_FILE), 'r') as f:
                node_group_data = json.load(f)
                node_group = nodes.write_shader_node_group(NODE_GROUP_NAME, node_group_data)
        
        image = props.output_image # can be None
        material_name = props.material_name

        if material_name != '' and material_name not in bpy.data.materials:
            nodes.create_material(
                material_name,
                node_group,
                image=image,
                uv_map=uv_map,
                sun_driver_obj=props.sun_driver,
                head_driver_obj=props.head_driver,
            )
            self.report({'INFO'}, 'Finished creating material!')
        else:
            self.report({'INFO'}, 'Material already exists, exiting operator.')
        
        return {'FINISHED'}

class CreateNodeGroupOnly(bpy.types.Operator):
    bl_idname = 'object.npr_shade_face_create_node_group'
    bl_label = 'NPR Shade Face Create Node Group Only'
    bl_description = 'Add a new node group to the project that allows for face shadow map usage.'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        if NODE_GROUP_NAME not in bpy.data.node_groups:
            with open(get_absolute_path(NODE_GROUP_FILE), 'r') as f:
                node_group_data = json.load(f)
                nodes.write_shader_node_group(NODE_GROUP_NAME, node_group_data)
            self.report({'INFO'}, 'Finished creating node group!')
        else:
            self.report({'INFO'}, 'Node group already exists, exiting operator.')
        
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

        col.separator()

        col.row(align=True).prop(props, 'material_name', text='Material Name')
        col.row(align=True).prop(props, 'uv_map_name', text='UV Map Name')

        col.separator()

        col.row(align=True).label(text='Driver Settings (Optional):')
        col.row(align=True).prop(props, 'sun_driver', text='Sun Driver Target')
        col.row(align=True).prop(props, 'head_driver', text='Head Driver Target')

        col.separator()

        col.row(align=True).operator(
            operator=ComputeFaceShadows.bl_idname,
            text='Generate Face Shading'
        )

        col.row(align=True).operator(
            operator=CreateMaterialOnly.bl_idname,
            text='Create Material Only'
        )

        col.row(align=True).operator(
            operator=CreateNodeGroupOnly.bl_idname,
            text='Create Node Group Only'
        )
