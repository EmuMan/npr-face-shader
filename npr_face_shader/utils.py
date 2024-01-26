from typing import Optional, Any, Callable
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

@dataclass
class BasePixelCalculator:
    width: int
    height: int
    intersection_points: npt.NDArray[np.float64]
    
    def __call__(self, index: int) -> float:
        x_index = index % self.width
        y_index = index // self.width
        x_position = x_index / self.width
        line_options = [(i, x_values[y_index]) for i, x_values in enumerate(self.intersection_points)]
        surrounding_lines = get_surrounding_values(x_position, line_options, key=lambda line: line[1])

        final_value = 0.0
        if surrounding_lines[0]:
            offset = (surrounding_lines[0][0] + 1) / (len(line_options) + 1)
            final_point = 1.0
            if surrounding_lines[1]:
                final_point = surrounding_lines[1][1]
            temp_value = (x_position - surrounding_lines[0][1]) / \
                        (final_point - surrounding_lines[0][1])
            final_value = offset + temp_value / (len(line_options) + 1)
        elif surrounding_lines[1]:
            final_value = (x_position / surrounding_lines[1][1]) / (len(line_options) + 1)
        
        return final_value


@dataclass
class ShapePixelCalculator:
    width: int
    height: int
    shape_center: npt.NDArray[np.float64]
    shape_max_distance_squared: float
    shape_points: list[npt.NDArray[np.float64]]

    def __call__(self, index: int) -> Optional[float]:
        x_index = index % self.width
        y_index = index // self.width
        position = np.array([x_index / self.width, y_index / self.height])
        ratio = find_value_inside_shape(position, self.shape_center, self.shape_max_distance_squared, self.shape_points)
        if not ratio:
            return None
        return ratio


@dataclass
class Simple3DFace:
    uvs: list[npt.NDArray[np.float64]]
    vertices: list[npt.NDArray[np.float64]]


@dataclass
class UVProjector:
    triangulated_mesh: list[Simple3DFace]
    mesh_matrix_world: npt.NDArray[np.float64]
    points_matrix_world: npt.NDArray[np.float64]

    def __call__(self, points: list[npt.NDArray[np.float64]]) -> Any:
        return project_points_to_uv(
            triangulated_mesh=self.triangulated_mesh,
            mesh_matrix_world=self.mesh_matrix_world,
            points=points,
            points_matrix_world=self.points_matrix_world,
        )


def clamp(n, smallest, largest): return smallest if n < smallest else largest if n > largest else n

def barycentric_coordinates(
        p: npt.NDArray[np.float64],
        a: npt.NDArray[np.float64],
        b: npt.NDArray[np.float64],
        c: npt.NDArray[np.float64],
        ) -> tuple[np.float64, np.float64, np.float64]:
    
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

def interpolate_point_barycentric(
        u: np.float64,
        v: np.float64,
        w: np.float64,
        val_a: npt.NDArray[np.float64],
        val_b: npt.NDArray[np.float64],
        val_c: npt.NDArray[np.float64],
        ) -> npt.NDArray[np.float64]:
    interpolated_value = u * val_a + v * val_b + w * val_c
    return interpolated_value

def get_closest_face(pos: npt.NDArray[np.float64], target_mesh: list[Simple3DFace], matrix_world: npt.NDArray[np.float64]) -> Optional[Simple3DFace]:
    closest_face = None
    closest_face_distance_squared = None
    
    for face in target_mesh:
        face_center = np.array([0.0, 0.0, 0.0])
        for vertex in face.vertices:
            vertex_loc = matrix_world @ np.array(vertex)
            face_center += vertex_loc
        
        face_center /= len(face.vertices)
        distance = face_center - pos
        distance_squared = distance.dot(distance)
        if not closest_face or distance_squared < closest_face_distance_squared:
            closest_face = face
            closest_face_distance_squared = distance_squared
    
    return closest_face

def get_furthest_vertex_distance(pos: npt.NDArray[np.float64], vertices: Iterable[npt.NDArray[np.float64]]) -> float:
    furthest_vertex_distance_squared = None
    for vertex_pos in vertices:
        distance = vertex_pos - pos
        distance_squared = distance.dot(distance)
        if not furthest_vertex_distance_squared or distance_squared > furthest_vertex_distance_squared:
            furthest_vertex_distance_squared = distance_squared
            
    return np.sqrt(furthest_vertex_distance_squared)

def get_surrounding_values(value: Any, options: Iterable[Any], key: Callable):
    previous_option = None
    options = sorted(options, key=key)
    for option in options:
        if key(option) > value:
            return (previous_option, option)
        previous_option = option
    return (previous_option, None)

def get_line_x_from_y(y: float, p1: npt.NDArray[np.float64], p2: npt.NDArray[np.float64]) -> float:
    d = (y - p1[1]) / (p2[1] - p1[1])
    return p2[0] * d + p1[0] * (1 - d)

def set_pixel(image_pixels: npt.NDArray[np.float64], index: int, color: float) -> None:
    image_pixels[index] = color

def get_pixel(image_pixels: npt.NDArray[np.float64], index: int) -> float:
    return image_pixels[index]

def set_pixel_blended(image_pixels: npt.NDArray[np.float64], index: int, color: float) -> None:
    image_pixels[index] = blend_overlay(image_pixels[index], color)
    
def blend_overlay(value_a: float, value_b: float) -> float:
    return (2 * value_a * value_b) if value_b else (1 - 2 * (1 - value_a) * (1 - value_b))

def project_points_to_uv(
        triangulated_mesh: list[Simple3DFace],
        mesh_matrix_world: npt.NDArray[np.float64],
        points: Iterable[npt.NDArray[np.float64]],
        points_matrix_world: npt.NDArray[np.float64],
        ) -> list[npt.NDArray[np.float64]]:
    
    projected: list[npt.NDArray[np.float64]] = []

    for initial_point in points:
        initial_point_pos = points_matrix_world @ initial_point
        closest_face = get_closest_face(initial_point_pos, triangulated_mesh, mesh_matrix_world)
        
        # Barycentric conversion then interpolation.
        triangle_a = closest_face.vertices[0]
        triangle_b = closest_face.vertices[1]
        triangle_c = closest_face.vertices[2]
        
        value_a = closest_face.uvs[0]
        value_b = closest_face.uvs[1]
        value_c = closest_face.uvs[2]
        
        input_point = np.array(initial_point_pos)
        
        u, v, w = barycentric_coordinates(input_point, triangle_a, triangle_b, triangle_c)
        final_uv = interpolate_point_barycentric(u, v, w, value_a, value_b, value_c)
        
        projected.append(final_uv)
    
    return projected

# TODO: perchance use numpy matrices to make this kewler
def get_intersection_point(
        segment_a: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
        segment_b: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        ) -> Optional[tuple[float, float, npt.NDArray[np.float64]]]:
    
    m1 = segment_a[1] - segment_a[0]
    b1 = segment_a[0]
    m2 = segment_b[1] - segment_b[0]
    b2 = segment_b[0]
    
    denom = (m2[0] * m1[1] - m1[0] * m2[1])
    if denom == 0:
        return None
    det = 1.0 / denom
    
    b2b1 = b2 - b1
    t1 = det * (m2[0] * b2b1[1] - m2[1] * b2b1[0])
    t2 = det * (m1[0] * b2b1[1] - m1[1] * b2b1[0])
    
    return (t1, t2, m1 * t1 + b1)

def close_2d_shape(points: Iterable[npt.NDArray[np.float64]]) -> list[npt.NDArray[np.float64]]:
    # close the loop temporarily by adding a closing edge
    points = list(points)
    points.append(points[0])
    
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
    return points

def find_2d_shape_center(points: list[npt.NDArray[np.float64]]) -> npt.NDArray[np.float64]:
    return sum(points, start=np.array([0.0, 0.0])) / len(points)

def find_2d_furthest_distance_squared(pos: npt.NDArray[np.float64], points: list[npt.NDArray[np.float64]]) -> float:
    distances = [pos - point for point in points]
    return max(map(lambda vec: vec.dot(vec), distances))

def find_value_inside_shape(
        position: npt.NDArray[np.float64],
        center: npt.NDArray[np.float64],
        max_distance_squared: float,
        points: list[npt.NDArray[np.float64]]
        ) -> float:
    
    distance = position - center
    
    # optimization, don't need to check all points
    if distance.dot(distance) > max_distance_squared:
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

def build_gaussian_kernel(size: int) -> npt.NDArray[np.float64]:
    # pascal's triangle is apparently a good approximation for this
    kernel = np.array([0.0] * size)
    kernel[0] = 1.0
    for i in range(1, size):
        kernel[i] = kernel[i - 1] * ((size - i) / i)
    return kernel / 2 ** (size - 1)

def build_box_kernel(size: int) -> npt.NDArray[np.float64]:
    return np.array([1.0 / size] * size)

def get_first_non_empty_array(arrays: list[list]) -> Optional[list]:
    for array in arrays:
        if array:
            return array
    return None

def find_average_x_value(points: list[npt.NDArray[np.float64]]) -> float:
    return sum([point[0] for point in points]) / len(points)
