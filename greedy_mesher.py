from atlas import Atlas
from collections import namedtuple
from fbx import FbxColor, FbxVector2, FbxVector4
from itertools import product
import numpy
#from qb import Matrix

__all__ = ['generate']

Vec3 = namedtuple('Vec3', 'x y z')
Quad = namedtuple('Quad', 'x y width height color')
Side = namedtuple('Side', 'normal up right clockwise')


class UVSlice(object):
    def __init__(self, index, count, width, height):
        self.index = index
        self.count = count
        self.width = width
        self.height = height


sides = [
    Side(Vec3(0, 1, 0), Vec3(0, 0, 1), Vec3(1, 0, 0), True),  # top
    Side(Vec3(0, -1, 0), Vec3(0, 0, 1), Vec3(1, 0, 0), False),  # bottom
    Side(Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1), True),  # right
    Side(Vec3(-1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1), False),  # left
    Side(Vec3(0, 0, 1), Vec3(0, 1, 0), Vec3(1, 0, 0), False),  # front
    Side(Vec3(0, 0, -1), Vec3(0, 1, 0), Vec3(1, 0, 0), True)  # back
]


def generate(matrix):
    size = matrix.size
    voxels = matrix.voxels

    uv_slices = []

    vertices = []
    indices = []
    uvs = []
    faces = []

    for side in sides:
        normal = side.normal
        right = side.right
        up = side.up

        stack_size = abs(normal.x) * size.x + abs(normal.y) * size.y + abs(normal.z) * size.z
        slice_width = abs(right.x) * size.x + abs(right.y) * size.y + abs(right.z) * size.z
        slice_height = abs(up.x) * size.x + abs(up.y) * size.y + abs(up.z) * size.z

        slice = numpy.empty(shape=(slice_width, slice_height), dtype=numpy.object)
        for _z in range(stack_size):
            for _x, _y in product(range(slice_width), range(slice_height)):
                x = right.x * _x + up.x * _y + abs(normal.x) * _z
                y = right.y * _x + up.y * _y + abs(normal.y) * _z
                z = right.z * _x + up.z * _y + abs(normal.z) * _z

                if voxels[x, y, z] is None:
                    continue

                if not 0 <= x + normal.x < size.x or \
                   not 0 <= y + normal.y < size.y or \
                   not 0 <= z + normal.z < size.z or \
                   voxels[x + normal.x, y + normal.y, z + normal.z] is None:
                        slice[_x, _y] = voxels[x, y, z]

            quads = []
            for _y in range(slice_height):
                _x = 0
                while _x < slice_width:
                    qc = slice[_x, _y]
                    if qc is not None:
                        qx, qy = _x, _y
                        qw, qh = 1, 1

                        while qx + qw < slice_width and slice[qx + qw, qy] == qc:
                            qw += 1

                        while qy + qh < slice_height:
                            k = 0
                            while k < qw and slice[qx + k, qy + qh] == qc:
                                k += 1
                            if k != qw:
                                break
                            qh += 1

                        quads.append(Quad(qx, qy, qw, qh, qc))
                        for x, y in product(range(qw), range(qh)):
                            slice[qx + x, qy + y] = None
                        _x += qw
                    else:
                        _x += 1

            uv_slice_index = len(vertices)
            for q in quads:
                _indices = [0, 1, 2, 3] if side.clockwise else [0, 3, 2, 1]

                for i in _indices:
                    indices.append(i + len(vertices))

                def make_vertex(x, y):
                    return FbxVector4(x * right.x + y * up.x + (_z + 0.5) * abs(normal.x) + 0.5 * normal.x,
                                      x * right.y + y * up.y + (_z + 0.5) * abs(normal.y) + 0.5 * normal.y,
                                      x * right.z + y * up.z + (_z + 0.5) * abs(normal.z) + 0.5 * normal.z)

                vertices.extend([
                    make_vertex(q.x, q.y),
                    make_vertex(q.x, q.y + q.height),
                    make_vertex(q.x + q.width, q.y + q.height),
                    make_vertex(q.x + q.width, q.y)
                ])

                uvs.extend([
                    FbxVector2(q.x, q.y),
                    FbxVector2(q.x, q.y + q.height),
                    FbxVector2(q.x + q.width, q.y + q.height),
                    FbxVector2(q.x + q.width, q.y),
                ])

                faces.append(q.color)

            uv_slices_count = len(vertices) - uv_slice_index
            if uv_slices_count > 0:
                uv_slices.append(UVSlice(uv_slice_index, uv_slices_count, slice_width, slice_height))

    # build uv map
    for u in uv_slices:
        min_x = max_x = uvs[u.index][0]
        min_y = max_y = uvs[u.index][1]
        for i in range(u.index + 1, u.index + u.count - 1):
            x, y = uvs[i]
            min_x, max_x = min(x, min_x), max(x, max_x)
            min_y, max_y = min(y, min_y), max(y, max_y)
        for i in range(u.index, u.index + u.count):
            uvs[i] = FbxVector2(uvs[i][0] - min_x, uvs[i][1] - min_y)
        u.width, u.height = max_x - min_x, max_y - min_y

    padding = 1
    s = 0
    for u in uv_slices:
        s += (u.width + padding) * (u.height + padding)
    map_size = 2
    while pow(map_size, 2) < s:
        map_size *= 2

    atlas = None
    while True:
        fit = True
        atlas = Atlas(map_size, map_size)
        for u in uv_slices:
            if not atlas.append(u.width + padding, u.height + padding, u):
                fit = False
                break
        if fit:
            break
        else:
            map_size *= 2

    for x, y, u in atlas:
        for i in range(u.index, u.index + u.count):
            uvs[i] = FbxVector2(uvs[i][0] + x, uvs[i][1] + y)

    # normalize uvs to [0..1]
    for i, uv in enumerate(uvs):
        uvs[i] = FbxVector2(uv[0] / map_size, uv[1] / map_size)

    return vertices, indices, uvs, faces
