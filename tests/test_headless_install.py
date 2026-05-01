from __future__ import annotations

import importlib
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


CORE_WRAPPER_ATTRIBUTES = [
    "vtkvmtkMath",
    "vtkvmtkPolyDataCenterlines",
    "vtkvmtkCenterlineAttributesFilter",
    "vtkvmtkCenterlineGeometry",
    "vtkvmtkVoronoiDiagram3D",
    "vtkvmtkPolyDataNetworkExtraction",
    "vtkvmtkPolyDataBoundaryExtractor",
]


@pytest.fixture()
def installed_import_context(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    tests_root = Path(__file__).resolve().parent

    for module_name in list(sys.modules):
        if module_name == "vmtk" or module_name.startswith("vmtk."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    filtered_path: list[str] = []
    for entry in sys.path:
        probe = Path(entry if entry else os.getcwd()).resolve()
        if probe in {repo_root, tests_root}:
            continue
        filtered_path.append(entry)

    if "" not in filtered_path:
        filtered_path.insert(0, "")

    monkeypatch.setattr(sys, "path", filtered_path)
    monkeypatch.chdir(tmp_path)


def assert_installed_location(module_file: str) -> None:
    normalized = module_file.replace("\\", "/")
    assert "/site-packages/" in normalized, (
        "module was not imported from site-packages: " + module_file
    )


def test_imports_vtk_and_vmtk_from_installed_package(installed_import_context):
    vtk = importlib.import_module("vtk")
    vmtk = importlib.import_module("vmtk")
    vtkvmtk = importlib.import_module("vmtk.vtkvmtk")

    assert vtk.vtkVersion.GetVTKVersion().startswith("9.5.")
    assert_installed_location(vmtk.__file__)

    missing = [name for name in CORE_WRAPPER_ATTRIBUTES if not hasattr(vtkvmtk, name)]
    assert missing == []


def test_vmtk_scripts_registry_is_importable(installed_import_context):
    scripts_registry = importlib.import_module("vmtk.vmtkscripts")

    assert "vmtk.vmtkcenterlines" in scripts_registry.__all__
    assert "vmtk.vmtkimagereader" in scripts_registry.__all__


def test_console_entrypoints_are_installed(installed_import_context, monkeypatch):
    python_bin_dir = str(Path(sys.executable).parent)
    monkeypatch.setenv(
        "PATH",
        python_bin_dir + os.pathsep + os.environ.get("PATH", ""),
    )

    assert shutil.which("vmtk") is not None
    assert shutil.which("vmtkimagereader") is not None

    proc = subprocess.run(
        ["vmtk", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "Usage:" in proc.stdout


def test_vmtk_image_shift_scale_processes_vtk_image(installed_import_context):
    vtk = importlib.import_module("vtk")
    imageshiftscale = importlib.import_module("vmtk.vmtkimageshiftscale")

    image = vtk.vtkImageData()
    image.SetDimensions(3, 3, 1)
    image.AllocateScalars(vtk.VTK_FLOAT, 1)

    scalars = image.GetPointData().GetScalars()
    for point_id in range(scalars.GetNumberOfTuples()):
        scalars.SetTuple1(point_id, float(point_id))

    shifter = imageshiftscale.vmtkImageShiftScale()
    shifter.Image = image
    shifter.Shift = 2.0
    shifter.Scale = 3.0
    shifter.OutputType = "float"
    shifter.Execute()

    output = shifter.Image.GetPointData().GetScalars()
    assert shifter.Image.GetScalarTypeAsString() == "float"
    assert output.GetTuple1(0) == pytest.approx(6.0)
    assert output.GetTuple1(8) == pytest.approx(30.0)


def test_vmtk_surface_mass_properties_processes_vtk_polydata(
    installed_import_context,
):
    vtk = importlib.import_module("vtk")
    massproperties = importlib.import_module("vmtk.vmtksurfacemassproperties")

    radius = 2.0
    source = vtk.vtkSphereSource()
    source.SetRadius(radius)
    source.SetThetaResolution(64)
    source.SetPhiResolution(32)
    source.Update()

    properties = massproperties.vmtkSurfaceMassProperties()
    properties.Surface = source.GetOutput()
    properties.Execute()

    assert properties.SurfaceArea == pytest.approx(4.0 * math.pi * radius**2, rel=1e-2)
    assert properties.Volume == pytest.approx(
        4.0 / 3.0 * math.pi * radius**3,
        rel=1e-2,
    )
    assert properties.ShapeIndex == pytest.approx(1.0, abs=1e-2)
