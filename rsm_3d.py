from __future__ import annotations

import json
import math
import struct

import numpy as np

from rsm_3d_obj import make_surface_obj_files
from rsm_config import APP_BUILD_VERSION
from rsm_core import FitResult


def _obj_material_colors(mtl_bytes: bytes) -> dict[str, tuple[float, float, float]]:
    colors: dict[str, tuple[float, float, float]] = {}
    current_material: str | None = None
    for raw_line in mtl_bytes.decode("utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("newmtl "):
            current_material = line.split(maxsplit=1)[1]
        elif current_material and line.startswith("Kd "):
            values = line.split()[1:4]
            if len(values) == 3:
                colors[current_material] = tuple(float(value) for value in values)
    return colors


def _obj_triangles_by_material(
    obj_bytes: bytes,
) -> dict[tuple[str, str], tuple[list[float], list[float]]]:
    vertices: list[np.ndarray] = []
    grouped_triangles: dict[tuple[str, str], tuple[list[float], list[float]]] = {}
    current_object = "RSM_Surface"
    current_material = "Default"

    for raw_line in obj_bytes.decode("utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("v "):
            values = line.split()[1:4]
            vertices.append(np.asarray([float(value) for value in values], dtype=float))
        elif line.startswith("o "):
            current_object = line.split(maxsplit=1)[1]
        elif line.startswith("usemtl "):
            current_material = line.split(maxsplit=1)[1]
        elif line.startswith("f "):
            face_indices = []
            for token in line.split()[1:]:
                vertex_token = token.split("/", 1)[0]
                vertex_index = int(vertex_token)
                face_indices.append(vertex_index - 1 if vertex_index > 0 else len(vertices) + vertex_index)
            if len(face_indices) < 3:
                continue

            position_values, normal_values = grouped_triangles.setdefault(
                (current_object, current_material),
                ([], []),
            )
            for index in range(1, len(face_indices) - 1):
                triangle = [
                    vertices[face_indices[0]],
                    vertices[face_indices[index]],
                    vertices[face_indices[index + 1]],
                ]
                normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
                normal_length = float(np.linalg.norm(normal))
                if normal_length <= 1e-12:
                    continue
                normal = normal / normal_length
                for vertex in triangle:
                    position_values.extend(float(value) for value in vertex)
                    normal_values.extend(float(value) for value in normal)
    return grouped_triangles


def _append_glb_float_view(
    binary: bytearray,
    buffer_views: list[dict[str, object]],
    accessors: list[dict[str, object]],
    values: list[float],
    *,
    include_bounds: bool,
) -> int:
    while len(binary) % 4:
        binary.append(0)
    byte_offset = len(binary)
    packed_values = np.asarray(values, dtype="<f4").tobytes()
    binary.extend(packed_values)
    buffer_view_index = len(buffer_views)
    buffer_views.append(
        {
            "buffer": 0,
            "byteOffset": byte_offset,
            "byteLength": len(packed_values),
            "target": 34962,
        }
    )
    accessor: dict[str, object] = {
        "bufferView": buffer_view_index,
        "componentType": 5126,
        "count": len(values) // 3,
        "type": "VEC3",
    }
    if include_bounds and values:
        reshaped = np.asarray(values, dtype=float).reshape(-1, 3)
        accessor["min"] = reshaped.min(axis=0).tolist()
        accessor["max"] = reshaped.max(axis=0).tolist()
    accessor_index = len(accessors)
    accessors.append(accessor)
    return accessor_index


def make_surface_glb(
    result: FitResult,
    axis_x: str,
    axis_y: str,
    fixed_values: dict[str, float],
    grid_size: int,
) -> bytes:
    obj_bytes, mtl_bytes = make_surface_obj_files(result, axis_x, axis_y, fixed_values, grid_size)
    colors = _obj_material_colors(mtl_bytes)
    triangles = _obj_triangles_by_material(obj_bytes)
    if not triangles:
        raise ValueError("GLB로 변환할 표면 삼각형이 없습니다.")

    binary = bytearray()
    buffer_views: list[dict[str, object]] = []
    accessors: list[dict[str, object]] = []
    materials: list[dict[str, object]] = []
    material_indices: dict[str, int] = {}
    grouped_primitives: dict[str, list[dict[str, object]]] = {"surface": [], "legend": []}

    for (object_name, material_name), (positions, normals) in triangles.items():
        if not positions:
            continue
        if material_name not in material_indices:
            red, green, blue = colors.get(material_name, (0.65, 0.65, 0.65))
            material_indices[material_name] = len(materials)
            materials.append(
                {
                    "name": material_name,
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [red, green, blue, 1.0],
                        "metallicFactor": 0.0,
                        "roughnessFactor": 0.72,
                    },
                    "doubleSided": True,
                }
            )
        material_index = material_indices[material_name]
        position_accessor = _append_glb_float_view(
            binary,
            buffer_views,
            accessors,
            positions,
            include_bounds=True,
        )
        normal_accessor = _append_glb_float_view(
            binary,
            buffer_views,
            accessors,
            normals,
            include_bounds=False,
        )
        group_name = "surface" if object_name == "RSM_Surface" else "legend"
        grouped_primitives[group_name].append(
            {
                "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
                "material": material_index,
                "mode": 4,
            }
        )

    while len(binary) % 4:
        binary.append(0)

    surface_tilt = math.radians(-52.0)
    nodes: list[dict[str, object]] = [{"name": "RSM Surface and Legend", "children": []}]
    meshes: list[dict[str, object]] = []

    if grouped_primitives["surface"]:
        surface_mesh_index = len(meshes)
        meshes.append(
            {
                "name": "RSM Surface",
                "primitives": grouped_primitives["surface"],
                "extras": {
                    "xAxis": axis_x,
                    "yAxis": axis_y,
                    "zAxis": result.y_label,
                    "fixedValues": fixed_values,
                },
            }
        )
        surface_node_index = len(nodes)
        nodes.append(
            {
                "mesh": surface_mesh_index,
                "name": "RSM Surface - Default 3/4 View",
                "rotation": [math.sin(surface_tilt / 2.0), 0.0, 0.0, math.cos(surface_tilt / 2.0)],
            }
        )
        nodes[0]["children"].append(surface_node_index)

    if grouped_primitives["legend"]:
        legend_mesh_index = len(meshes)
        meshes.append(
            {
                "name": "Viridis 3D Legend",
                "primitives": grouped_primitives["legend"],
            }
        )
        legend_node_index = len(nodes)
        nodes.append({"mesh": legend_mesh_index, "name": "Viridis Legend - Front Facing"})
        nodes[0]["children"].append(legend_node_index)

    gltf = {
        "asset": {
            "version": "2.0",
            "generator": f"DOE RSM App {APP_BUILD_VERSION}",
        },
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }

    json_chunk = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((-len(json_chunk)) % 4)
    binary_chunk = bytes(binary)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    return b"".join(
        [
            struct.pack("<4sII", b"glTF", 2, total_length),
            struct.pack("<I4s", len(json_chunk), b"JSON"),
            json_chunk,
            struct.pack("<I4s", len(binary_chunk), b"BIN\x00"),
            binary_chunk,
        ]
    )


