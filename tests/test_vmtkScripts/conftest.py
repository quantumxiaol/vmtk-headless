## Program: VMTK
## Language:  Python
## Date:      January 10, 2018
## Version:   1.4

##   Copyright (c) Richard Izzo, Luca Antiga, All rights reserved.
##   See LICENSE file for details.

##      This software is distributed WITHOUT ANY WARRANTY; without even
##      the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
##      PURPOSE.  See the above copyright notices for more information.

## Note: this code was contributed by
##       Richard Izzo (Github @rlizzo)
##       University at Buffalo

from __future__ import print_function
import pytest
import os
import copy
from hashlib import sha1
import vtk

import vmtk.vmtkimagereader as imagereader
import vmtk.vmtkimagetonumpy as imagetonumpy
import vmtk.vmtkimagewriter as imagewriter
import vmtk.vmtkimagecompare as imagecompare

import vmtk.vmtksurfacereader as surfacereader
import vmtk.vmtksurfacetonumpy as surfacetonumpy
import vmtk.vmtksurfacecompare as surfacecompare
import vmtk.vmtksurfacewriter as surfacewriter

import vmtk.vmtkmeshreader as meshreader
import vmtk.vmtkmeshwriter as meshwriter
import vmtk.vmtkmeshcompare as meshcompare
from vmtk import vtkvmtk


ITK_WRAPPERS_AVAILABLE = hasattr(vtkvmtk, 'vtkvmtkITKArchetypeImageSeriesScalarReader')
SEGMENTATION_WRAPPERS_AVAILABLE = hasattr(vtkvmtk, 'vtkvmtkVesselnessMeasureImageFilter')
RENDERING_WRAPPERS_AVAILABLE = hasattr(vtkvmtk, 'vtkvmtkInteractorStyleTrackballCamera')
VTK_VERSION = tuple(int(part) for part in vtk.vtkVersion.GetVTKVersion().split('.')[:2])

SEGMENTATION_TEST_MODULES = {
    'test_vmtkcenterlineimage.py',
    'test_vmtkimagefeatures.py',
    'test_vmtkimagemorphology.py',
    'test_vmtkimagenormalize.py',
    'test_vmtkimageobjectenhancement.py',
    'test_vmtkimageotsuthresholds.py',
    'test_vmtkimagevesselenhancement.py',
    'test_vmtklevelsetsegmentation.py',
}

RENDERING_TEST_MODULES = {
    'test_vmtkimagevolumeviewer.py',
}

ITK_DEPENDENT_TEST_MODULES = {
    'test_vmtkimagevoiselector.py',
    'test_vmtksurfacetransformtoras.py',
}

CRASH_PRONE_TEST_MODULES = {
    'test_vmtksurfaceremeshing.py',
}


def pytest_collection_modifyitems(config, items):
    if not SEGMENTATION_WRAPPERS_AVAILABLE:
        skip_segmentation = pytest.mark.skip(
            reason='Segmentation wrappers are disabled in this build.'
        )
        for item in items:
            if item.fspath.basename in SEGMENTATION_TEST_MODULES:
                item.add_marker(skip_segmentation)

    if not RENDERING_WRAPPERS_AVAILABLE:
        skip_rendering = pytest.mark.skip(
            reason='Rendering wrappers are disabled in this build.'
        )
        for item in items:
            if item.fspath.basename in RENDERING_TEST_MODULES:
                item.add_marker(skip_rendering)

    if not ITK_WRAPPERS_AVAILABLE:
        skip_itk = pytest.mark.skip(
            reason='ITK reader wrappers are disabled in this build.'
        )
        for item in items:
            if item.fspath.basename == 'test_vmtkimagereader.py' and 'test_read_dicom_image' in item.nodeid:
                item.add_marker(skip_itk)
            if item.fspath.basename in ITK_DEPENDENT_TEST_MODULES:
                item.add_marker(skip_itk)

    if VTK_VERSION >= (9, 5):
        skip_crashy = pytest.mark.skip(
            reason='Known native instability with VTK 9.5+ in dependency-minimized builds.'
        )
        for item in items:
            if item.fspath.basename in CRASH_PRONE_TEST_MODULES:
                item.add_marker(skip_crashy)


@pytest.fixture(scope='module')
def input_datadir():
    '''
    returns a path to the vmtk/tests/testData directory
    '''
    try:
        datadir = os.path.join(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.realpath(__file__))), 'vmtk-test-data', 'input')
        if not os.path.isdir(datadir): raise ValueError()
    except ValueError:
        datadir = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.realpath(__file__))))),
            'vmtk-test-data', 'input')
        if not os.path.isdir(datadir):
            raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
    return datadir


# **************************************************
# Image Functions
# **************************************************


@pytest.fixture(scope='module')
def aorta_image(input_datadir):
    reader = imagereader.vmtkImageReader()
    reader.UseITKIO = 0
    reader.InputFileName = os.path.join(input_datadir, 'aorta.mha')
    reader.Execute()
    return reader.Image


# this is a hack because pytest doesn't currently let you define functions
# with inputs as fixtures. This way we return a function which accepts the input
# and returns the sha.
@pytest.fixture(scope='module')
def image_to_sha():
    def make_image_to_sha(image):
        converter = imagetonumpy.vmtkImageToNumpy()
        converter.Image = image
        converter.Execute()
        point_data = converter.ArrayDict['PointData']
        scalar_key = 'ImageScalars' if 'ImageScalars' in point_data else next(iter(point_data.keys()))
        check = point_data[scalar_key].copy(order='C')
        return sha1(check).hexdigest()
    return make_image_to_sha


@pytest.fixture(scope='module')
def write_image():
    def make_write_image(image, filename):
        writer = imagewriter.vmtkImageWriter()
        writer.Image = image
        try:
            datadir = os.path.join(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))), 'vmtk-test-data', 'imagereference')
            if not os.path.isdir(datadir): raise ValueError()
        except ValueError:
            datadir = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))))),
                'vmtk-test-data', 'imagereference')
            if not os.path.isdir(datadir):
                raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
        writer.OutputFileName = os.path.join(datadir, filename)
        writer.Execute()
        return
    return make_write_image


@pytest.fixture(scope='module')
def compare_images():
    def make_compare_images(image, reference_file, tolerance=0.1):
        reader = imagereader.vmtkImageReader()
        reader.UseITKIO = 0
        try:
            datadir = os.path.join(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))), 'vmtk-test-data', 'imagereference')
            if not os.path.isdir(datadir): raise ValueError()
        except ValueError:
            datadir = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))))),
                'vmtk-test-data', 'imagereference')
            if not os.path.isdir(datadir):
                raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
        reader.InputFileName = os.path.join(datadir, reference_file)
        reader.Execute()

        comp = imagecompare.vmtkImageCompare()
        comp.Image = image
        comp.ReferenceImage = reader.Image
        comp.Method = 'subtraction'
        comp.Tolerance = tolerance
        comp.Execute()

        return comp.Result
    return make_compare_images


# **************************************************
# Surface Functions
# **************************************************


@pytest.fixture(scope='module')
def aorta_surface(input_datadir):
    reader = surfacereader.vmtkSurfaceReader()
    reader.InputFileName = os.path.join(input_datadir, 'aorta-surface.vtp')
    reader.Execute()
    return reader.Surface


@pytest.fixture(scope='module')
def aorta_surface2(input_datadir):
    reader = surfacereader.vmtkSurfaceReader()
    reader.InputFileName = os.path.join(input_datadir, 'aorta-surface-segment-2.stl')
    reader.Execute()
    return reader.Surface


@pytest.fixture(scope='module')
def aorta_surface_openends(input_datadir):
    reader = surfacereader.vmtkSurfaceReader()
    reader.InputFileName = os.path.join(input_datadir, 'aorta-surface-open-ends.stl')
    reader.Execute()
    return reader.Surface


@pytest.fixture(scope='module')
def aorta_surface_branches(input_datadir):
    reader = surfacereader.vmtkSurfaceReader()
    reader.InputFileName = os.path.join(input_datadir, 'aorta-surface-branch-split.vtp')
    reader.Execute()
    return reader.Surface


@pytest.fixture(scope='module')
def aorta_surface_reference(input_datadir):
    reader = surfacereader.vmtkSurfaceReader()
    reader.InputFileName = os.path.join(input_datadir, 'aorta-surface-connectivity-reference.stl')
    reader.Execute()
    return reader.Surface


@pytest.fixture()
def poly_to_np(scope='module'):
    def make_poly_to_np(surface):
        converter = surfacetonumpy.vmtkSurfaceToNumpy()
        converter.Surface = surface
        converter.Execute()
        return converter.ArrayDict
    return make_poly_to_np


@pytest.fixture(scope='module')
def write_surface():
    def make_write_surface(surface, filename):
        writer = surfacewriter.vmtkSurfaceWriter()
        writer.Surface = surface
        try:
            datadir = os.path.join(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))), 'vmtk-test-data', 'surfacereference')
            if not os.path.isdir(datadir): raise ValueError()
        except ValueError:
            datadir = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))))),
                'vmtk-test-data', 'surfacereference')
            if not os.path.isdir(datadir):
                raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
        writer.OutputFileName = os.path.join(datadir, filename)
        writer.Execute()
        return
    return make_write_surface


@pytest.fixture(scope='module')
def compare_surfaces():
    def make_compare_surface(surface, reference_file, tolerance=0.001, method='distance', arrayname=''):
        reader = surfacereader.vmtkSurfaceReader()
        try:
            datadir = os.path.join(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))), 'vmtk-test-data', 'surfacereference')
            if not os.path.isdir(datadir): raise ValueError()
        except ValueError:
            datadir = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))))),
                'vmtk-test-data', 'surfacereference')
            if not os.path.isdir(datadir):
                raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
        reader.InputFileName = os.path.join(datadir, reference_file)
        reader.Execute()

        comp = surfacecompare.vmtkSurfaceCompare()
        comp.Surface = surface
        comp.ReferenceSurface = reader.Surface
        comp.Method = method
        comp.ArrayName = arrayname
        comp.Tolerance = tolerance
        comp.Execute()

        return comp.Result
    return make_compare_surface


# *************************************************
# Centerlines
# *************************************************

@pytest.fixture(scope='module')
def aorta_centerline(input_datadir):
    reader = surfacereader.vmtkSurfaceReader()
    reader.InputFileName = os.path.join(input_datadir, 'aorta-centerline.vtp')
    reader.Execute()
    return reader.Surface


@pytest.fixture(scope='module')
def aorta_centerline_branches(input_datadir):
    reader = surfacereader.vmtkSurfaceReader()
    reader.InputFileName = os.path.join(input_datadir, 'aorta-centerline-branches.vtp')
    reader.Execute()
    return reader.Surface


@pytest.fixture(scope='module')
def write_centerline():
    def make_write_centerline(centerline, filename):
        writer = surfacewriter.vmtkSurfaceWriter()
        writer.Surface = centerline
        try:
            datadir = os.path.join(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))), 'vmtk-test-data', 'centerlinereference')
            if not os.path.isdir(datadir): raise ValueError()
        except ValueError:
            datadir = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))))),
                'vmtk-test-data', 'centerlinereference')
            if not os.path.isdir(datadir):
                raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
        writer.OutputFileName = os.path.join(datadir, filename)
        writer.Execute()
        return
    return make_write_centerline


@pytest.fixture(scope='module')
def compare_centerlines():
    def make_compare_centerline(centerline, reference_file, tolerance=0.001, method='distance', arrayname=''):
        reader = surfacereader.vmtkSurfaceReader()
        try:
            datadir = os.path.join(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))), 'vmtk-test-data', 'centerlinereference')
            if not os.path.isdir(datadir): raise ValueError()
        except ValueError:
            datadir = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.realpath(__file__))))),
                'vmtk-test-data', 'centerlinereference')
            if not os.path.isdir(datadir):
                raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
        reader.InputFileName = os.path.join(datadir, reference_file)
        reader.Execute()

        comp = surfacecompare.vmtkSurfaceCompare()
        comp.Surface = centerline
        comp.ReferenceSurface = reader.Surface
        comp.Method = method
        comp.ArrayName = arrayname
        comp.Tolerance = tolerance
        comp.Execute()

        return comp.Result
    return make_compare_centerline


# **************************************************
# Mesh Functions
# **************************************************

@pytest.fixture(scope='module')
def aorta_mesh(input_datadir):
    reader = meshreader.vmtkMeshReader()
    reader.InputFileName = os.path.join(input_datadir, 'aorta-mesh.vtu')
    reader.Execute()
    return reader.Mesh


@pytest.fixture(scope='module')
def write_mesh():
    def make_write_mesh(mesh, filename):
        writer = meshwriter.vmtkMeshWriter()
        writer.Mesh = mesh
        try:
            datadir = '@ExternalData_BINARY_ROOT@/tests/data/meshreference'
            if not os.path.isdir(datadir): raise ValueError()
        except ValueError:
            try:
                datadir = '@ExternalData_BINARY_ROOT@'
                datadir = datadir.replace('/work/build/ExternalData', '/test_tmp/build/ExternalData/tests/data/meshreference')
                if not os.path.isdir(datadir): raise ValueError()
            except ValueError:
                datadir = os.path.join(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.dirname(
                                    os.path.realpath(__file__))))),
                    'vmtk-test-data/meshreference')
                if not os.path.isdir(datadir):
                    raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
        writer.OutputFileName = os.path.join(datadir, filename)
        writer.Execute()
        return
    return make_write_mesh


@pytest.fixture(scope='module')
def compare_meshes():
    def make_compare_meshes(mesh, reference_file, tolerance=0.001, method='cellarray', arrayname=''):
        reader = meshreader.vmtkMeshReader()
        try:
            datadir = '@ExternalData_BINARY_ROOT@/tests/data/meshreference'
            if not os.path.isdir(datadir): raise ValueError()
        except ValueError:
            try:
                datadir = '@ExternalData_BINARY_ROOT@'
                datadir = datadir.replace('/work/build/ExternalData', '/test_tmp/build/ExternalData/tests/data/meshreference')
                if not os.path.isdir(datadir): raise ValueError()
            except ValueError:
                datadir = os.path.join(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(
                                os.path.dirname(
                                    os.path.realpath(__file__))))),
                    'vmtk-test-data/meshreference')
                if not os.path.isdir(datadir):
                    raise ValueError('the vmtk-test-data repository cannot be found at the same level as vmtk. expected it to be at', datadir)
        reader.InputFileName = os.path.join(datadir, reference_file)
        reader.Execute()

        comp = meshcompare.vmtkMeshCompare()
        comp.Mesh = mesh
        comp.ReferenceMesh = reader.Mesh
        comp.Method = method
        comp.ArrayName = arrayname
        comp.Tolerance = tolerance
        comp.Execute()

        return comp.Result
    return make_compare_meshes
