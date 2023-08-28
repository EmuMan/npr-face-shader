import bpy
from mathutils import Vector
import bmesh

from typing import Optional
import multiprocessing as mp
from dataclasses import dataclass
import math

import numpy as np


@dataclass
class BasePixelCalculator:
    width: int
    height: int
    intersection_points: list[int]
    
    def __call__(self, index: int):
        x = index % self.width
        y = index // self.width
        position = Vector((x / self.width, y / self.height))
        line_options = [(i, x_values[y]) for i, x_values in enumerate(self.intersection_points)]
        return get_surrounding_values(position.x, line_options, key=lambda line: line[1])


def clamp(n, smallest, largest): return smallest if n < smallest else largest if n > largest else n

def barycentric_coordinates(p, a, b, c):
    v0 = b - a
    v1 = c - a
    v2 = p - a
    
    d00 = np.dot(v0, v0)
    d01 = np.dot(v0, v1)
    d11 = np.dot(v1, v1)
    d20 = np.dot(v2, v0)
    d21 = np.dot(v2, v1)
    
    denom = d00 * d11 - d01 * d01
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    
    return u, v, w

def interpolate_point_barycentric(u, v, w, val_a, val_b, val_c):
    interpolated_value = u * val_a + v * val_b + w * val_c
    return interpolated_value

def get_closest_face(pos: Vector, target_mesh: bmesh, matrix_world):
    closest_face = None
    closest_face_distance_squared = None
    closest_face_center = None
    
    for face in target_mesh['faces']:
        face_center = Vector()
        for vertex in face.verts:
            vertex_loc = matrix_world @ vertex.co
            face_center += vertex_loc
        
        face_center /= len(face.verts)
        distance = face_center - pos
        if not closest_face or distance.length_squared < closest_face_distance_squared:
            closest_face = face
            closest_face_distance_squared = distance.length_squared
            closest_face_center = face_center
    
    return closest_face, closest_face_center

def get_furthest_vertex_distance(pos: Vector, vertices: list) -> float:
    furthest_vertex_distance_squared = None
    for vertex_pos in vertices:
        distance = vertex_pos - pos
        distance_squared = distance.length_squared
        if not furthest_vertex_distance_squared or distance_squared > furthest_vertex_distance_squared:
            furthest_vertex_distance_squared = distance_squared
            
    return math.sqrt(furthest_vertex_distance_squared)

def get_surrounding_values(value, options, key):
    previous_option = None
    options = sorted(options, key=key)
    for option in options:
        if key(option) > value:
            return (previous_option, option)
        previous_option = option
    return (previous_option, None)

def get_line_x_from_y(y: float, p1: Vector, p2: Vector) -> Vector:
    d = (y - p1.y) / (p2.y - p1.y)
    return p2.x * d + p1.x * (1 - d)

def set_pixel(image_pixels, width, height, position, color):
    pixel_location = Vector((int(position.x * width), int(position.y * height)))
    offset = pixel_location.x + pixel_location.y * width
    image_pixels[int(offset)] = color

def get_pixel(image_pixels, width, height, position) -> float:
    pixel_location = Vector((int(position.x * width), int(position.y * height)))
    offset = pixel_location.x + pixel_location.y * width
    return image_pixels[int(offset)]

def set_pixel_blended(image_pixels, width, height, position, color):
    pixel_location = Vector((int(position.x * width), int(position.y * height)))
    offset = int(pixel_location.x + pixel_location.y * width)
    image_pixels[offset] = blend_overlay(image_pixels[offset], color)
    
def blend_overlay(value_a: float, value_b: float) -> float:
    return (2 * value_a * value_b) if value_b else (1 - 2 * (1 - a) * (1 - b))

def project_points_to_uv(original_mesh, triangulated_mesh, mesh_matrix_world, points, points_matrix_world):
    projected = []
    for initial_point in points:
        initial_point_pos = points_matrix_world @ initial_point.co
        closest_face, closest_face_center = \
            get_closest_face(initial_point_pos, triangulated_mesh, mesh_matrix_world)
        closest_face_verts = [v.co for v in closest_face.verts]
        
        # Barycentric conversion then interpolation.
        # ChatGPT wrote all this code. I basically wrote none of it.
        # It works perfectly.
        # My career is doomed.
        triangle_a = np.array(closest_face_verts[0])
        triangle_b = np.array(closest_face_verts[1])
        triangle_c = np.array(closest_face_verts[2])
        
        value_a = closest_face.loops[0][original_mesh.loops.layers.uv.active].uv
        value_b = closest_face.loops[1][original_mesh.loops.layers.uv.active].uv
        value_c = closest_face.loops[2][original_mesh.loops.layers.uv.active].uv
        
        input_point = np.array(initial_point_pos)
        
        u, v, w = barycentric_coordinates(input_point, triangle_a, triangle_b, triangle_c)
        interpolated = interpolate_point_barycentric(u, v, w, value_a, value_b, value_c)
        final_uv = Vector(interpolated)
        final_uv.freeze()
        
        projected.append(final_uv)
    return projected

def get_intersection_point(segment_a, segment_b) -> Optional[tuple[float, float, Vector]]:
    m1 = segment_a[1] - segment_a[0]
    b1 = segment_a[0]
    m2 = segment_b[1] - segment_b[0]
    b2 = segment_b[0]
    
    denom = (m2.x * m1.y - m1.x * m2.y)
    if denom == 0:
        return None
    det = 1.0 / denom
    
    b2b1 = b2 - b1
    t1 = det * (m2.x * b2b1.y - m2.y * b2b1.x)
    t2 = det * (m1.x * b2b1.y - m1.y * b2b1.x)
    
    return (t1, t2, m1 * t1 + b1)

def close_2d_shape(points: list[Vector]) -> list[Vector]:
    # close the loop temporarily by adding a closing edge
    final_points = points[:] + [points[0]]
    
    # can't do anything on the first point
    for i in range(1, len(points)):
        # scan every segment up to i for an intersection
        # + don't check segment before i because that will
        # always be connected at the endpoint
        # also can't do anything on the first line segment
        for j in range(1, i - 1):
            intersection_point = get_intersection_point(
                (points[i-1], points[i]), (points[j-1], points[j]))
            if not intersection_point:
                # lines are parallel
                continue
            int_t1, int_t2, int_point = intersection_point
            if int_t1 < 0.0 or int_t1 > 1.0 or int_t2 < 0.0 or int_t2 > 1.0:
                # lines intersect outside range
                continue
            # an intersection was found!
            # set the last point in the loop to this intersection
            points[i] = int_point
            # set the first point in the loop to this intersection
            points[j-1] = int_point
            # return only the points in the loop
            return points[j-1:i+1]
    # there was no intersection found, so the basic loop can be returned
    return final_points

def find_2d_shape_center(points: list[Vector]) -> Vector:
    return sum(points, start=Vector((0.0, 0.0))) / len(points)

def find_2d_furthest_distance_squared(pos: Vector, points: list[Vector]) -> float:
    return max(points, key=lambda point: (pos - point).length_squared)

def find_value_inside_shape(position: Vector, center: Vector, max_distance_squared: float, points: list[Vector]) -> float:
    distance = position - center
    
    # optimization, don't need to check all points
    if distance.length_squared > max_distance_squared:
        return None
    
    ray_vec = (center, position)
    for i in range(1, len(points)):
        segment = (points[i-1], points[i])
        current_intersection = get_intersection_point(ray_vec, segment)
        if not current_intersection:
            continue
        
        # collision vector is LONGER than the ray vector,
        # and within the bounds of the segment
        if current_intersection[0] > 1.0 and \
            current_intersection[1] >= 0.0 and \
            current_intersection[1] <= 1.0:
            return 1.0 / current_intersection[0]
        
    # ray does not have a bounding point
    return None

def main():
    target_name = 'face'
    target_obj = bpy.data.objects.get(target_name)
    
    face_lines_name = 'Face Lines'
    face_lines_obj = bpy.data.objects.get(face_lines_name)
    face_lines_layer = face_lines_obj.data.layers[0]
    face_lines_strokes = face_lines_layer.frames[0].strokes
    
    nose_line_name = 'Nose Line'
    nose_line_obj = bpy.data.objects.get(nose_line_name)
    nose_line_layer = nose_line_obj.data.layers[0]
    nose_line_stroke = nose_line_layer.frames[0].strokes[0]
    
    rembrandt_line_name = 'Rembrandt Line'
    rembrandt_line_obj = bpy.data.objects.get(rembrandt_line_name)
    rembrandt_line_layer = rembrandt_line_obj.data.layers[0]
    rembrandt_line_stroke = rembrandt_line_layer.frames[0].strokes[0]
    
    # mesh has to be triangulated for barycentric conversion to work
    print('Triangulating mesh...')
    bm = bmesh.new()
    bm.from_mesh(target_obj.data)
    triangulated = bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    
    lines_on_image = []
    print('Mapping face strokes to UV coordinates...')
    for stroke in face_lines_strokes:
        lines_on_image.append(project_points_to_uv(bm, triangulated, target_obj.matrix_world, stroke.points, face_lines_obj.matrix_world))
    
    image = bpy.data.images['Face Shadow']
    width = image.size[0]
    height = image.size[1]
    
    # The image is grayscale so this is fine
    image_pixels = [0.0 for _ in range(width * height)]
    
    print('Finding row intersection points...')
    intersection_points = []
    for line in lines_on_image:
        intersections_for_line = []
        for i in range(height):
            segments = get_surrounding_values(i / height, line, lambda point: point.y)
            if not segments[0]:
                intersections_for_line.append(segments[1].x)
            elif not segments[1]:
                intersections_for_line.append(segments[0].x)
            else:
                intersections_for_line.append(get_line_x_from_y(i / height, segments[0], segments[1]))
        intersection_points.append(intersections_for_line)
    
    print('Calculating base pixels...')
    for x in range(width):
        for y in range(height):
            position = Vector((x / width, y / height))
            line_options = [(i, x_values[y]) for i, x_values in enumerate(intersection_points)]
            surrounding_lines = get_surrounding_values(position.x, line_options, key=lambda line: line[1])
            
            final_value = 0.0
            if surrounding_lines[0]:
                offset = (surrounding_lines[0][0] + 1) / (len(line_options) + 1)
                final_point = 1.0
                if surrounding_lines[1]:
                    final_point = surrounding_lines[1][1]
                temp_value = (position.x - surrounding_lines[0][1]) / \
                            (final_point - surrounding_lines[0][1])
                final_value = offset + temp_value / (len(line_options) + 1)
            elif surrounding_lines[1]:
                final_value = (position.x / surrounding_lines[1][1]) / (len(line_options) + 1)
            
            set_pixel(image_pixels, width, height, position, final_value)
    
    nose_on_image = []
    print('Mapping nose stroke to UV coordinates...')
    nose_on_image = project_points_to_uv(bm, triangulated, target_obj.matrix_world, nose_line_stroke.points, nose_line_obj.matrix_world)
    
    print('Closing off nose shape...')
    nose_on_image = close_2d_shape(nose_on_image)
    
    print('Calculating nose pixels...')
    # many multipliers are so the effective area of the nose is expanded
    nose_center = find_2d_shape_center(nose_on_image)
    nose_max_distance_squared = find_2d_furthest_distance_squared(nose_center, nose_on_image)
    for x in range(width):
        for y in range(height):
            position = Vector((x / width, y / height))
            ratio = find_value_inside_shape(position, nose_center, nose_max_distance_squared, nose_on_image)
            if not ratio:
                continue
            pixel_value = ratio ** 2 / 2.0
            set_pixel_blended(image_pixels, width, height, position, pixel_value)
    
    rembrandt_on_image = []
    print('Mapping Rembrandt stroke to UV coordinates...')
    rembrandt_on_image = project_points_to_uv(bm, triangulated, target_obj.matrix_world, rembrandt_line_stroke.points, rembrandt_line_obj.matrix_world)
    
    print('Closing off Rembrandt shape...')
    rembrandt_on_image = close_2d_shape(rembrandt_on_image)
    
    print('Calculating Rembrandt pixels...')
    rembrandt_center = find_2d_shape_center(rembrandt_on_image)
    rembrandt_max_distance_squared = find_2d_furthest_distance_squared(rembrandt_center, rembrandt_on_image)
    for x in range(width):
        for y in range(height):
            position = Vector((x / width, y / height))
            ratio = find_value_inside_shape(position, rembrandt_center, rembrandt_max_distance_squared, rembrandt_on_image)
            if not ratio:
                continue
            pixel_value = (1 - ratio ** 2) / 2.0 + 0.5
            set_pixel_blended(image_pixels, width, height, position, pixel_value)
    
    print('Updating image...')
    converted = []
    for pixel in image_pixels:
        converted.extend([pixel, pixel, pixel, 1.0])
    image.pixels[:] = converted
    
    print('Done!')

if __name__ == '__main__':
    main()
