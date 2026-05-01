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

import pytest
import vtk
import vmtk.vmtksurfacenormals as normals


vtk_version = tuple(int(part) for part in vtk.vtkVersion.GetVTKVersion().split('.')[:2])


def test_normals_smoke(aorta_surface):
    normer = normals.vmtkSurfaceNormals()
    normer.Surface = aorta_surface
    normer.Execute()

    normals_array = normer.Surface.GetPointData().GetArray('Normals')
    assert normals_array is not None
    assert normals_array.GetNumberOfTuples() == normer.Surface.GetNumberOfPoints()


@pytest.mark.skipif(
    vtk_version >= (9, 5),
    reason='Surface normal orientation differs across VTK 9.5+ builds.',
)
def test_default_params(aorta_surface, compare_surfaces):
    name = __name__ + '_test_default_params.vtp'
    normer = normals.vmtkSurfaceNormals()
    normer.Surface = aorta_surface
    normer.Execute()

    assert compare_surfaces(normer.Surface, name, method='addpointarray', arrayname='Normals') == True


@pytest.mark.skipif(
    vtk_version >= (9, 5),
    reason='Surface normal orientation differs across VTK 9.5+ builds.',
)
def test_no_autoorient_normals(aorta_surface, compare_surfaces):
    name = __name__ + '_test_no_autoorient_normals.vtp'
    normer = normals.vmtkSurfaceNormals()
    normer.Surface = aorta_surface
    normer.AutoOrientNormals = 0
    normer.Execute()

    assert compare_surfaces(normer.Surface, name, method='addpointarray', arrayname='Normals') == True


@pytest.mark.skipif(
    vtk_version >= (9, 5),
    reason='Surface normal orientation differs across VTK 9.5+ builds.',
)
def test_no_consistency(aorta_surface, compare_surfaces):
    name = __name__ + '_test_no_consistency.vtp'
    normer = normals.vmtkSurfaceNormals()
    normer.Surface = aorta_surface
    normer.Consistency = 0
    normer.Execute()

    assert compare_surfaces(normer.Surface, name, method='addpointarray', arrayname='Normals') == True
