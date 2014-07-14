import argparse
from fbx import *
import greedy_mesher
from itertools import product
import numpy
import os
import qb

__all__ = ['convert']


def generate_mesh(scene, matrix, generate_uv):
    vertices, indices, uvs, faces = greedy_mesher.generate(matrix)    
    
    mesh = FbxMesh.Create(scene, matrix.name)

    layer = mesh.GetLayer(0)
    if not layer:
        mesh.CreateLayer()
        layer = mesh.GetLayer(0)

    mesh.InitControlPoints(len(vertices))
    for i, vertex in enumerate(vertices):
        mesh.SetControlPointAt(vertex, i)
        
    for i in range(len(indices) / 4):
        mesh.BeginPolygon(i)
        for j in range(4):
            mesh.AddPolygon(indices[i*4+j])
        mesh.EndPolygon()

    if generate_uv:
        uv_layer = FbxLayerElementUV.Create(mesh, '')
        uv_layer.SetMappingMode(FbxLayerElement.eByControlPoint)
        uv_layer.SetReferenceMode(FbxLayerElement.eDirect)
        for uv in uvs:
            uv_layer.GetDirectArray().Add(uv)
        layer.SetUVs(uv_layer)

    colors_layer = FbxLayerElementVertexColor.Create(mesh, '')
    colors_layer.SetMappingMode(FbxLayerElement.eByControlPoint)
    colors_layer.SetReferenceMode(FbxLayerElement.eDirect)

    mat_layer = FbxLayerElementMaterial.Create(mesh, '')
    mat_layer.SetMappingMode(FbxLayerElement.eByPolygon)
    mat_layer.SetReferenceMode(FbxLayerElement.eIndexToDirect)

    for f in faces:
        c = FbxColor(f.r / 255.0, f.g / 255.0, f.b / 255.0, 1.0)
        for i in range(4):
            colors_layer.GetDirectArray().Add(c)
        mat_layer.GetIndexArray().Add(f.material)
    layer.SetVertexColors(colors_layer)
    layer.SetMaterials(mat_layer)

    return mesh


def convert(filename, destination, generate_uv=False, merge_meshes=False):
    fbx_manager = FbxManager.Create()
    fbx_scene = FbxScene.Create(fbx_manager, '')

    root_node = fbx_scene.GetRootNode()

    matrices = []
    with open(filename, 'rb') as f:
        reader = qb.reader(f)
        for matrix in reader:
            matrices.append(matrix)

    materials = []
    for matrix in matrices:
        material = FbxSurfacePhong.Create(fbx_manager, matrix.name)
        materials.append(material)

    if merge_meshes:
        name = os.path.splitext(os.path.basename(filename))[0]
        pos = None
        size = None
        voxels = None
        for i, matrix in enumerate(matrices):
            if voxels is None:
                pos = matrix.pos
                size = matrix.size
                voxels = numpy.copy(matrix.voxels)
            else:
                min_x = min(pos.x, matrix.pos.x)
                min_y = min(pos.y, matrix.pos.y)
                min_z = min(pos.z, matrix.pos.z)
                max_x = max(pos.x + size.x, matrix.pos.x + matrix.size.x)
                max_y = max(pos.y + size.y, matrix.pos.y + matrix.size.y)
                max_z = max(pos.z + size.z, matrix.pos.z + matrix.size.z)

                new_pos = qb.Vec3(min_x, min_y, min_z)
                new_size = qb.Vec3(max_x - min_x, max_y - min_y, max_z - min_z)
                new_voxels = numpy.empty(shape=(new_size.x, new_size.y, new_size.z), dtype=numpy.object)

                dx, dy, dz = pos.x - new_pos.x, pos.y - new_pos.y, pos.z - new_pos.z
                for x, y, z in product(range(size.x), range(size.y), range(size.z)):
                    v = voxels[x, y, z]
                    if v is not None:
                        new_voxels[x + dx, y + dy, z + dz] = v

                dx, dy, dz = matrix.pos.x - new_pos.x, matrix.pos.y - new_pos.y, matrix.pos.z - new_pos.z
                for x, y, z in product(range(matrix.size.x), range(matrix.size.y), range(matrix.size.z)):
                    v = matrix.voxels[x, y, z]
                    if v is not None:
                        v.material = i
                        new_voxels[x + dx, y + dy, z + dz] = v
                pos = new_pos
                size = new_size
                voxels = new_voxels

        matrices = [qb.Matrix(name, pos, size, voxels)]

    for i, matrix in enumerate(matrices):
        mesh = generate_mesh(fbx_scene, matrix, generate_uv)        

        node = FbxNode.Create(fbx_scene, matrix.name)
        node.LclTranslation.Set(FbxDouble3(matrix.pos.x, matrix.pos.y, matrix.pos.z))
        node.SetNodeAttribute(mesh)
        root_node.AddChild(node)

        if merge_meshes:
            for m in materials:
                node.AddMaterial(m)
        else:
            node.AddMaterial(materials[i])

    exporter = FbxExporter.Create(fbx_manager, '')
    if not exporter.Initialize(destination):
        raise Exception('Exporter failed to initialize. Error returned: ' + exporter.GetLastErrorString())
    exporter.Export(fbx_scene)
    exporter.Destroy()

    fbx_manager.Destroy()
    del fbx_scene
    del fbx_manager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='input QB file')
    parser.add_argument('-o', '--output', help='output FBX file')
    parser.add_argument('-uv', '--generate-uv', help='generate UV map', action='store_true')
    parser.add_argument('-j', '--merge-meshes', help='merge meshes to a single mesh', action='store_true')
    args = parser.parse_args()

    filename = args.filename
    output = args.output if args.output is not None else os.path.splitext(filename)[0] + '.fbx'

    convert(filename, output, args.generate_uv, args.merge_meshes)

if __name__ == '__main__':
    main()