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
import vmtk.vmtkmarchingcubes as marchingcubes


@pytest.fixture()
def level_set_image(input_datadir):
    import vmtk.vmtkimagereader as reader
    import os
    read = reader.vmtkImageReader()
    read.UseITKIO = 0
    read.InputFileName = os.path.join(input_datadir, 'aorta-final-levelset.mha')
    read.Execute()

    return read.Image


def test_marching_cubes_default(level_set_image):
    mc = marchingcubes.vmtkMarchingCubes()
    mc.Image = level_set_image
    mc.Level = 0.0
    mc.Execute()

    assert mc.Surface.GetNumberOfPoints() == 6468
    assert mc.Surface.GetNumberOfCells() == 12932
    assert mc.Surface.GetBounds() == pytest.approx(
        (-107.271416, -72.967461, 48.449776, 132.406631, 12.454676, 35.359859),
        abs=1e-5,
    )
