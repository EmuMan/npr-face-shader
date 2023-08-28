import bpy
import bmesh

from multiprocessing.pool import Pool

from .utils import *

def create_face_shadow_map(pool: Pool):
    target_name = 'face'
    target_obj = bpy.data.objects.get(target_name)
    target_matrix_world = np.array(target_obj.matrix_world)[0:3, 0:3]
    
    face_lines_name = 'Face Lines'
    face_lines_obj = bpy.data.objects.get(face_lines_name)
    face_lines_layer = face_lines_obj.data.layers[0]
    face_lines_strokes = face_lines_layer.frames[0].strokes
    face_lines_matrix_world = np.array(face_lines_obj.matrix_world)[0:3, 0:3]
    
    nose_line_name = 'Nose Line'
    nose_line_obj = bpy.data.objects.get(nose_line_name)
    nose_line_layer = nose_line_obj.data.layers[0]
    nose_line_stroke = nose_line_layer.frames[0].strokes[0]
    nose_line_matrix_world = np.array(nose_line_obj.matrix_world)[0:3, 0:3]
    
    rembrandt_line_name = 'Rembrandt Line'
    rembrandt_line_obj = bpy.data.objects.get(rembrandt_line_name)
    rembrandt_line_layer = rembrandt_line_obj.data.layers[0]
    rembrandt_line_stroke = rembrandt_line_layer.frames[0].strokes[0]
    rembrandt_line_matrix_world = np.array(rembrandt_line_obj.matrix_world)[0:3, 0:3]

    blur_size = 25
    
    image = bpy.data.images['Face Shadow']
    width = image.size[0]
    height = image.size[1]
    
    # The image is grayscale so this is fine
    image_pixels = np.array([0.0 for _ in range(width * height)])
    
    # mesh has to be triangulated for barycentric conversion to work
    print('Triangulating mesh...')
    bm = bmesh.new()
    bm.from_mesh(target_obj.data)
    triangulated = bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    
    simplified_target_mesh: list[Simple3DFace] = []
    for face in triangulated['faces']:
        simplified_target_mesh.append(Simple3DFace(
            uvs=[np.array(loop[bm.loops.layers.uv.active].uv) for loop in face.loops],
            vertices=[np.array(vert.co) for vert in face.verts],
        ))

    lines_on_image = []
    print('Mapping face strokes to UV coordinates...')
    uv_projector = UVProjector(
        triangulated_mesh=simplified_target_mesh,
        mesh_matrix_world=target_matrix_world,
        points_matrix_world=face_lines_matrix_world,
    )
    
    face_lines_strokes = [[np.array(point.co) for point in stroke.points] for stroke in face_lines_strokes]
    lines_on_image = pool.map(uv_projector, face_lines_strokes)
    
    print('Finding row intersection points...')
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
    
    print('Calculating base pixels...')

    base_pixel_calculator = BasePixelCalculator(width, height, intersection_points)
    image_pixels[:] = pool.map(base_pixel_calculator, range(width * height))

    nose_on_image = []
    print('Mapping nose stroke to UV coordinates...')
    nose_line_stroke_points = [np.array(point.co) for point in nose_line_stroke.points]
    nose_on_image = project_points_to_uv(
        triangulated_mesh=simplified_target_mesh,
        mesh_matrix_world=target_matrix_world,
        points=nose_line_stroke_points,
        points_matrix_world=nose_line_matrix_world,
    )
    
    print('Closing off nose shape...')
    nose_on_image = close_2d_shape(nose_on_image)
    
    print('Calculating nose pixels...')
    nose_center = find_2d_shape_center(nose_on_image)
    nose_max_distance_squared = find_2d_furthest_distance_squared(nose_center, nose_on_image)
    
    nose_pixel_calculator = ShapePixelCalculator(
        width=width,
        height=height,
        shape_center=nose_center,
        shape_max_distance_squared=nose_max_distance_squared,
        shape_points=nose_on_image,
    )

    nose_pixels = pool.map(nose_pixel_calculator, range(width * height))
    for i, value in enumerate(nose_pixels):
        if value is not None:
            set_pixel_blended(image_pixels, i, value ** 2 / 2.0)
    
    rembrandt_on_image = []
    print('Mapping Rembrandt stroke to UV coordinates...')
    rembrandt_line_stroke_points = [np.array(point.co) for point in rembrandt_line_stroke.points]
    rembrandt_on_image = project_points_to_uv(
        triangulated_mesh=simplified_target_mesh,
        mesh_matrix_world=target_matrix_world,
        points=rembrandt_line_stroke_points,
        points_matrix_world=rembrandt_line_matrix_world,
    )
    
    print('Closing off Rembrandt shape...')
    rembrandt_on_image = close_2d_shape(rembrandt_on_image)
    
    print('Calculating Rembrandt pixels...')
    rembrandt_center = find_2d_shape_center(rembrandt_on_image)
    rembrandt_max_distance_squared = find_2d_furthest_distance_squared(rembrandt_center, rembrandt_on_image)

    rembrandt_pixel_calculator = ShapePixelCalculator(
        width=width,
        height=height,
        shape_center=rembrandt_center,
        shape_max_distance_squared=rembrandt_max_distance_squared,
        shape_points=rembrandt_on_image,
    )
    
    rembrandt_pixels = pool.map(rembrandt_pixel_calculator, range(width * height))
    for i, value in enumerate(rembrandt_pixels):
        if value is not None:
            set_pixel_blended(image_pixels, i, (1 - value ** 2) / 2.0 + 0.5)

    print('Blurring final result...')
    gaussian_kernel = build_box_kernel(blur_size)
    image_pixels_2d = image_pixels.reshape((height, width))
    image_pixels_2d = np.apply_along_axis(lambda x: np.convolve(x, gaussian_kernel, mode='same'), 0, image_pixels_2d)
    image_pixels_2d = np.apply_along_axis(lambda x: np.convolve(x, gaussian_kernel, mode='same'), 1, image_pixels_2d)
    image_pixels = image_pixels_2d.reshape(width * height)
    
    print('Updating image...')
    converted = []
    for value in image_pixels:
        converted.extend([value, value, value, 1.0])
    image.pixels[:] = converted
    
    print('Done!')
