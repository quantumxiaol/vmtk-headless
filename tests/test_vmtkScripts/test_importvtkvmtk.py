## Program: VMTK
## Language:  Python

import pytest


CORE_WRAPPER_ATTRIBUTES = [
    'vtkvmtkMath',
    'vtkvmtkPolyDataCenterlines',
    'vtkvmtkCenterlineAttributesFilter',
    'vtkvmtkCenterlineGeometry',
    'vtkvmtkVoronoiDiagram3D',
    'vtkvmtkPolyDataNetworkExtraction',
    'vtkvmtkPolyDataBoundaryExtractor',
]


def test_import_vtk_runtime():
    import vtk

    assert isinstance(vtk.vtkVersion.GetVTKVersion(), str)


def test_import_vtkvmtk_core_symbols():
    from vmtk import vtkvmtk

    for name in CORE_WRAPPER_ATTRIBUTES:
        assert hasattr(vtkvmtk, name)


def test_import_vtkvmtk_optional_groups_are_self_consistent():
    from vmtk import vtkvmtk

    # Segmentation classes are optional in dependency-minimized builds.
    # Use segmentation-owned symbols as probes (LevelSetSigmoid lives in Misc).
    if hasattr(vtkvmtk, 'vtkvmtkOtsuMultipleThresholdsImageFilter'):
        assert hasattr(vtkvmtk, 'vtkvmtkAnisotropicDiffusionImageFilter')

    # Rendering classes are optional in headless builds.
    if hasattr(vtkvmtk, 'vtkvmtkInteractorStyleTrackballCamera'):
        assert hasattr(vtkvmtk, 'vtkvmtkImagePlaneWidget')

    # TetGen wrappers are optional when TetGen support is disabled.
    if hasattr(vtkvmtk, 'vtkvmtkTetGenReader'):
        assert hasattr(vtkvmtk, 'vtkvmtkTetGenWriter')


def test_itk_version_when_itk_wrapper_available():
    from vmtk import vtkvmtk

    if not hasattr(vtkvmtk, 'vtkvmtkITKVersion'):
        pytest.skip('ITK wrapper support is disabled in this build.')

    itk_version = vtkvmtk.vtkvmtkITKVersion
    assert isinstance(itk_version.GetITKVersion(), str)
