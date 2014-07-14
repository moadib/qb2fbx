from collections import namedtuple
from itertools import product
import numpy
from struct import unpack


__all__ = ['reader', 'Color', 'Matrix', 'QubicleReader']


Header = namedtuple('Header', 'version color_format z_axis_orientation compressed visibility_mask_encoded num_matrices')
Vec3 = namedtuple('Vec3', 'x y z')
Matrix = namedtuple('Matrix', 'name pos size voxels')


class Voxel(object):
    def __init__(self, r, g, b, material=0):
        self.r = r
        self.g = g
        self.b = b
        self.material = material

    def __eq__(self, other):
        return other is not None and \
            self.r == other.r and \
            self.g == other.g and \
            self.b == other.b and \
            self.material == other.material


class QubicleReader(object):
    def __init__(self, f):
        header = Header(*unpack('<IIIIII', f.read(24)))
        
        self.file = f
        self.color_format = header.color_format
        self.compressed = header.compressed
        self.num_matrices = header.num_matrices
        self.i = -1

    def _unpack_color(self, value):
        if value == 0:
            return None
        r = value & 0xFF
        g = (value >> 8) & 0xFF
        b = (value >> 16) & 0xFF                        
        return Voxel(r, g, b) if self.color_format == 0 else Voxel(b, g, r)

    def _read_matrix(self, f):
        name_len = unpack('B', f.read(1))[0]
        name = f.read(name_len)
        size = Vec3(*unpack('<III', f.read(12)))
        pos = Vec3(*unpack('<iii', f.read(12)))

        voxels = numpy.empty(shape=(size.x, size.y, size.z), dtype=numpy.object)
        if self.compressed == 0:  # uncompressed
            for x, y, z in product(range(size.x), range(size.y), range(size.z)):
                data = unpack('<I', f.read(4))[0]
                voxels[x, y, z] = self._unpack_color(data)
        else:  # compressed
            for z in range(size.z):
                index = 0
                while True:
                    data = unpack('<I', f.read(4))[0]
                    if data == 6:  # next slice
                        break
                    elif data == 2:  # code
                        count = unpack('<I', f.read(4))[0]
                        data = unpack('<I', f.read(4))[0]
                        for j in range(count):
                            x = index % size.x
                            y = index / size.x
                            index += 1
                            voxels[x, y, z] = self._unpack_color(data)
                    else:
                        x = index % size.x
                        y = index / size.x
                        index += 1
                        voxels[x, y, z] = self._unpack_color(data)

        return Matrix(name, pos, size, voxels)

    def __iter__(self):
        return self

    def next(self):
        if self.i < self.num_matrices - 1:
            self.i += 1                     
            return self._read_matrix(self.file)
        else:
            raise StopIteration


def reader(f):
    return QubicleReader(f)