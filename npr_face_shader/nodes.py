import bpy

from typing import Any

def set_specified_attributes(target: Any, attributes: dict[str, Any]) -> None:
    for attribute, value in attributes.items():
        setattr(target, attribute, value)

def write_shader_node_group(name: str, data: dict[str, list[dict[str, Any]]]) -> None:
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
        set_specified_attributes(node, node_data)
        nodes.append(node)
    
    for link_data in data['links']:
        link = tree.links.new(
            nodes[link_data.pop('from_node')].outputs[link_data.pop('from_socket')],
            nodes[link_data.pop('to_node')].inputs[link_data.pop('to_socket')])
        set_specified_attributes(link, link_data)
