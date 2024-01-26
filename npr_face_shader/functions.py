import bpy
import bmesh

from multiprocessing.pool import Pool

from .utils import *

def verify_property(prop: bpy.types.PointerProperty | None, data_class: bpy.types.ID):
    return prop is not None and isinstance(prop.data, data_class)

def create_face_shadow_map(operator: bpy.types.Operator, pool: Pool):
    props = bpy.data.objects[0].face_shade_props

    target_obj = props.target
    if not verify_property(target_obj, bpy.types.Mesh):
        operator.report({'ERROR'}, 'Target object must be a valid mesh.')
        return
    target_matrix_world = np.array(target_obj.matrix_world)[0:3, 0:3]

    bm = bmesh.new()
    bm.from_mesh(target_obj.data)

    if props.uv_map_name == '':
        uv_map = bm.loops.layers.uv.active
    else:
        try:
            uv_map = bm.loops.layers.uv[props.uv_map_name]
        except KeyError:
            operator.report({'ERROR'}, 'Invalid UV map name for target mesh.')
            return
    
    face_lines_obj = props.vertical_lines
    if not verify_property(face_lines_obj, bpy.types.GreasePencil):
        operator.report({'ERROR'}, 'Vertical lines must be a valid grease pencil.')
        return
    face_lines_strokes = get_first_non_empty_array(
        [layer.frames[0].strokes for layer in face_lines_obj.data.layers])
    face_lines_matrix_world = np.array(face_lines_obj.matrix_world)[0:3, 0:3]
    
    shadow_shapes_obj = props.shadow_shapes
    if not verify_property(shadow_shapes_obj, bpy.types.GreasePencil):
        operator.report({'ERROR'}, 'Shadow shapes must be a valid grease pencil.')
        return
    shadow_shapes_strokes = get_first_non_empty_array(
        [layer.frames[0].strokes for layer in shadow_shapes_obj.data.layers])
    shadow_shapes_matrix_world = np.array(shadow_shapes_obj.matrix_world)[0:3, 0:3]
    
    highlight_shapes_obj = props.highlight_shapes
    if not verify_property(highlight_shapes_obj, bpy.types.GreasePencil):
        operator.report({'ERROR'}, 'Highlight shapes must be a valid grease pencil.')
        return
    highlight_shapes_strokes = get_first_non_empty_array(
        [layer.frames[0].strokes for layer in highlight_shapes_obj.data.layers])
    highlight_shapes_matrix_world = np.array(highlight_shapes_obj.matrix_world)[0:3, 0:3]

    blur_size = props.blur_size
    
    image = props.output_image
    if image is None:
        operator.report({'ERROR'}, 'Output image must be set.')
    width = image.size[0]
    height = image.size[1]
    
    # The image is grayscale so this is fine
    image_pixels = np.array([0.0 for _ in range(width * height)])
    
    # mesh has to be triangulated for barycentric conversion to work
    operator.report({'INFO'}, 'Triangulating mesh...')
    triangulated = bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')

    simplified_target_mesh: list[Simple3DFace] = []
    for face in triangulated['faces']:
        simplified_target_mesh.append(Simple3DFace(
            uvs=[np.array(loop[uv_map].uv) for loop in face.loops],
            vertices=[np.array(vert.co) for vert in face.verts],
        ))

    lines_on_image = []
    operator.report({'INFO'}, 'Mapping face strokes to UV coordinates...')
    uv_projector = UVProjector(
        triangulated_mesh=simplified_target_mesh,
        mesh_matrix_world=target_matrix_world,
        points_matrix_world=face_lines_matrix_world,
    )
    
    face_lines_strokes = [[np.array(point.co) for point in stroke.points] for stroke in face_lines_strokes]
    lines_on_image = pool.map(uv_projector, face_lines_strokes)
    
    operator.report({'INFO'}, 'Finding row intersection points...')
    intersection_points = []
    for line in lines_on_image:
        intersections_for_line = []
        for i in range(height):
            segments = get_surrounding_values(i / height, line, lambda point: point[1])
            if segments[0] is None:
                intersections_for_line.append(segments[1][0])
            elif segments[1] is None:
                intersections_for_line.append(segments[0][0])
            else:
                intersections_for_line.append(get_line_x_from_y(i / height, segments[0], segments[1]))
        intersection_points.append(intersections_for_line)
    
    operator.report({'INFO'}, 'Calculating base pixels...')

    base_pixel_calculator = BasePixelCalculator(width, height, intersection_points)
    image_pixels[:] = pool.map(base_pixel_calculator, range(width * height))

    shadow_shapes_on_image: list[list[npt.NDArray[np.float64]]] = []
    operator.report({'INFO'}, 'Mapping shadow shapes to UV coordinates...')
    for stroke in shadow_shapes_strokes:
        shadow_shape_stroke_points = [np.array(point.co) for point in stroke.points]
        projected_points = project_points_to_uv(
            triangulated_mesh=simplified_target_mesh,
            mesh_matrix_world=target_matrix_world,
            points=shadow_shape_stroke_points,
            points_matrix_world=shadow_shapes_matrix_world,
        )
        shadow_shapes_on_image.append(projected_points)
    
    operator.report({'INFO'}, 'Closing off shadow shapes...')
    shadow_shapes_on_image[:] = [close_2d_shape(shape) for shape in shadow_shapes_on_image]
    
    operator.report({'INFO'}, 'Calculating shadow pixels...')
    for shape in shadow_shapes_on_image:
        shape_center = find_2d_shape_center(shape) 
        shape_max_distance_squared = find_2d_furthest_distance_squared(shape_center, shape)
        
        pixel_calculator = ShapePixelCalculator(
            width=width,
            height=height,
            shape_center=shape_center,
            shape_max_distance_squared=shape_max_distance_squared,
            shape_points=shape,
        )

        shadow_pixels = pool.map(pixel_calculator, range(width * height))
        for i, value in enumerate(shadow_pixels):
            if value is not None:
                set_pixel_blended(image_pixels, i, value ** 2 / 2.0)
    
    highlight_shapes_on_image: list[list[npt.NDArray[np.float64]]] = []
    operator.report({'INFO'}, 'Mapping highlight shapes to UV coordinates...')
    for stroke in highlight_shapes_strokes:
        highlight_shape_stroke_points = [np.array(point.co) for point in stroke.points]
        projected_points = project_points_to_uv(
            triangulated_mesh=simplified_target_mesh,
            mesh_matrix_world=target_matrix_world,
            points=highlight_shape_stroke_points,
            points_matrix_world=highlight_shapes_matrix_world,
        )
        highlight_shapes_on_image.append(projected_points)
    
    operator.report({'INFO'}, 'Closing off shadow shapes...')
    highlight_shapes_on_image[:] = [close_2d_shape(shape) for shape in highlight_shapes_on_image]
    
    operator.report({'INFO'}, 'Calculating shadow pixels...')
    for shape in highlight_shapes_on_image:
        shape_center = find_2d_shape_center(shape)
        shape_max_distance_squared = find_2d_furthest_distance_squared(shape_center, shape)

        pixel_calculator = ShapePixelCalculator(
            width=width,
            height=height,
            shape_center=shape_center,
            shape_max_distance_squared=shape_max_distance_squared,
            shape_points=shape,
        )
        
        highlight_pixels = pool.map(pixel_calculator, range(width * height))
        for i, value in enumerate(highlight_pixels):
            if value is not None:
                set_pixel_blended(image_pixels, i, (1 - value ** 2) / 2.0 + 0.5)

    operator.report({'INFO'}, 'Blurring final result...')
    gaussian_kernel = build_box_kernel(blur_size)
    image_pixels_2d = image_pixels.reshape((height, width))
    image_pixels_2d = np.apply_along_axis(lambda x: np.convolve(x, gaussian_kernel, mode='same'), 0, image_pixels_2d)
    image_pixels_2d = np.apply_along_axis(lambda x: np.convolve(x, gaussian_kernel, mode='same'), 1, image_pixels_2d)
    image_pixels = image_pixels_2d.reshape(width * height)
    
    operator.report({'INFO'}, 'Updating image...')
    converted = []
    for value in image_pixels:
        converted.extend([value, value, value, 1.0])
    image.pixels[:] = converted

    operator.report({'INFO'}, 'Finished!')
