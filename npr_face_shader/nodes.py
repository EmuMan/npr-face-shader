import bpy
import mathutils

from typing import Any

def set_specified_attributes(target: Any, attributes: dict[str, Any]) -> None:
    for attribute, value in attributes.items():
        setattr(target, attribute, value)

def write_shader_node_group(name: str, data: dict[str, list[dict[str, Any]]]) -> bpy.types.NodeTree:
    tree = bpy.data.node_groups.new(name=name, type='ShaderNodeTree')
    
    for input_data in data['inputs']:
        input_type = input_data.pop('type')
        _input = tree.inputs.new(name=input_data['name'], type=input_type)
        set_specified_attributes(_input, input_data)
    
    for output_data in data['outputs']:
        output_type = output_data.pop('type')
        output = tree.outputs.new(name=output_data['name'], type=output_type)
        set_specified_attributes(output, output_data)
    
    nodes: list[bpy.types.NodeInternal] = []
    for node_data in data['nodes']:
        node_type = node_data.pop('type')
        parent_index = node_data.pop('parent')
        node = tree.nodes.new(type=node_type)
        if parent_index is not None:
            # pretty sure all frames are before all nodes,
            # so no IndexErrors should occur
            node.parent = nodes[parent_index]
        for i, input_default in enumerate(node_data.pop('input_defaults')):
            if input_default is not None:
                node.inputs[i].default_value = input_default
        for i, output_default in enumerate(node_data.pop('output_defaults')):
            if output_default is not None:
                node.outputs[i].default_value = output_default
        set_specified_attributes(node, node_data)
        nodes.append(node)
    
    for link_data in data['links']:
        link = tree.links.new(
            nodes[link_data.pop('from_node')].outputs[link_data.pop('from_socket')],
            nodes[link_data.pop('to_node')].inputs[link_data.pop('to_socket')])
        set_specified_attributes(link, link_data)
    
    return tree

def create_material(name: str, shadows_node_tree: bpy.types.NodeTree, image: bpy.types.Image = None, uv_map: str = '') -> None:
    new_material = bpy.data.materials.new(name=name)
    new_material.use_nodes = True
    new_material.node_tree.nodes.remove(new_material.node_tree.nodes[0])

    node_group: bpy.types.ShaderNodeGroup = new_material.node_tree.nodes.new(type='ShaderNodeGroup')
    node_group.location = mathutils.Vector((302.1086, 195.7629))
    node_group.node_tree = shadows_node_tree
    material_output_node = new_material.node_tree.nodes['Material Output']
    material_output_node.location = mathutils.Vector((513.5494, 127.4066))
    uv_map_node = new_material.node_tree.nodes.new(type='ShaderNodeUVMap')
    uv_map_node.location = mathutils.Vector((-487.1404, 143.6472))
    uv_map_node.uv_map = uv_map
    mapping_normal_node = new_material.node_tree.nodes.new(type='ShaderNodeMapping')
    mapping_normal_node.location = mathutils.Vector((-239.7573, 424.1311))
    mapping_flipped_node = new_material.node_tree.nodes.new(type='ShaderNodeMapping')
    mapping_flipped_node.location = mathutils.Vector((-241.4846, 53.3045))
    mapping_flipped_node.inputs[3].default_value = mathutils.Vector((-1.0, 1.0, 1.0))
    image_normal_node = new_material.node_tree.nodes.new(type='ShaderNodeTexImage')
    image_normal_node.location = mathutils.Vector((-18.7990, 337.3714))
    image_normal_node.image = image
    image_flipped_node = new_material.node_tree.nodes.new(type='ShaderNodeTexImage')
    image_flipped_node.location = mathutils.Vector((-18.6186, -13.8533))
    image_flipped_node.image = image
    
    new_material.node_tree.links.new(uv_map_node.outputs[0], mapping_normal_node.inputs[0])
    new_material.node_tree.links.new(uv_map_node.outputs[0], mapping_flipped_node.inputs[0])
    new_material.node_tree.links.new(mapping_normal_node.outputs[0], image_normal_node.inputs[0])
    new_material.node_tree.links.new(mapping_flipped_node.outputs[0], image_flipped_node.inputs[0])
    new_material.node_tree.links.new(image_normal_node.outputs[0], node_group.inputs[3])
    new_material.node_tree.links.new(image_flipped_node.outputs[0], node_group.inputs[4])
    new_material.node_tree.links.new(node_group.outputs[0], material_output_node.inputs[0])
