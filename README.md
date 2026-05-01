# vmtk-headless

`vmtk-headless` is an unofficial, dependency-minimized Python packaging of
[VMTK, the Vascular Modeling Toolkit](https://www.vmtk.org/).

The PyPI/distribution package name is `vmtk-headless`, but the Python import
name stays compatible with upstream VMTK:

```python
import vmtk
from vmtk import vtkvmtk
```

The command line tools also keep the upstream names, for example `vmtk`,
`vmtkimagereader`, `vmtksurfacereader`, and `vmtkcenterlines`.

This fork is meant for non-interactive Python, CLI, CI, container, and server
workflows where the original conda/superbuild and GUI-oriented dependency stack
is too heavy.

## About VMTK

VMTK is a collection of libraries and command line tools for image-based
vascular modeling. It is commonly used for 3D reconstruction, centerline
extraction, Voronoi-based geometric analysis, surface processing, mesh
generation, and branch/bifurcation measurements.

Upstream VMTK can be used as a C++ library, a Python package, a set of PypeS
command line tools, and through GUI-oriented workflows such as 3D Slicer
integration. Those upstream workflows are broader than this package. This
`vmtk-headless` fork keeps the parts that are useful in automated, non-GUI
Python and CLI environments, while intentionally dropping heavyweight GUI,
rendering, ITK segmentation, and TetGen build requirements from the default
wheel.

Typical VMTK concepts still relevant here include:

- Centerlines and maximum-inscribed-sphere radius arrays.
- Voronoi diagrams and branch extraction.
- Surface cleaning, smoothing, remeshing, capping, clipping, and mass
  properties.
- Mesh and surface readers/writers for VTK-oriented data formats.
- PypeS pipelines for chaining command line tools without intermediate scripts.

## What This Fork Changes

Compared with upstream VMTK, this package:

- Uses a PEP 517 build backend through `scikit-build-core`.
- Builds as the PyPI package `vmtk-headless` while installing the import package
  `vmtk`.
- Targets Python `3.10.*` and VTK `9.5.0`.
- Builds directly against a system/SDK VTK instead of using the VMTK superbuild.
- Installs VMTK Python modules, PypeS modules, native `vtkvmtk` Python wrappers,
  and CLI launchers into a normal Python wheel layout.
- Disables GUI/rendering, ITK-backed segmentation, and TetGen by default.
- Avoids checking out `tests/vmtk-test-data` during package installation.
- Provides smoke tests for import, CLI entrypoints, and basic in-memory VTK data
  processing.

The goal is packaging reliability, not feature parity with the full upstream
desktop/conda distribution.

## What Is Included

The default build keeps the core non-GUI VMTK libraries and scripts:

- Native `vtkvmtk` Python wrappers.
- Core C++ modules: `Common`, `ComputationalGeometry`,
  `DifferentialGeometry`, `IO`, and `Misc`.
- PypeS runtime and script piping.
- `vmtkScripts` and Python contrib scripts.
- Centerline and Voronoi algorithms such as
  `vtkvmtkPolyDataCenterlines` and `vtkvmtkVoronoiDiagram3D`.
- Surface and mesh geometry utilities such as branch extraction, bifurcation
  metrics, smoothing, remeshing, mass properties, projection, clipping, readers,
  and writers.
- Image utilities that only depend on VTK, such as image read/write, cast,
  shift/scale, compose, marching cubes, and related simple processing.

Some Python script files that are installed for upstream compatibility may still
reference disabled native classes. Importing the script module can succeed while
executing a specific mode can fail if it needs a disabled feature.

## What Is Not Included

The default headless build intentionally leaves out:

- Rendering/OpenGL/X11 VMTK classes:
  `vtkvmtkImagePlaneWidget`, `vtkvmtkInteractorStyleTrackballCamera`, and
  related rendering wrappers are not built.
- Interactive viewer workflows:
  `vmtksurfaceviewer`, `vmtkimageviewer`, `vmtkrenderer`, interactive seed
  picking, and GUI-style tools are not supported as headless workflows.
- ITK-backed segmentation classes:
  level set segmentation, vesselness filters, ITK image wrappers, and other
  classes from `vtkVmtk/Segmentation` are not built.
- TetGen:
  `vtkvmtkTetGenWrapper` is not built.
- Native C++ contrib classes:
  Python contrib scripts are installed, but `vtkVmtk/Contrib` native wrappers
  are not built by default.
- Static temporal stream tracer:
  VMTK's static temporal stream tracer is disabled with VTK `9.5.0`.
- Upstream full test-data checkout:
  the large `tests/vmtk-test-data` submodule is skipped during normal package
  installs.

If your workflow needs interactive rendering, Slicer integration, ITK-backed
segmentation, or TetGen-specific features, use upstream VMTK or patch this
fork's forced CMake defaults and build with the required native dependencies.

## Install

Python `3.10.*` is required.

From PyPI:

```bash
uv add vmtk-headless
```

or:

```bash
python -m pip install vmtk-headless
```

From this Git repository:

```bash
uv pip install "vmtk-headless @ git+https://github.com/quantumxiaol/vmtk-headless.git"
```

or:

```bash
python -m pip install "vmtk-headless @ git+https://github.com/quantumxiaol/vmtk-headless.git"
```

Do not write the direct reference as `vmtk @ git+...`. The distribution metadata
name is `vmtk-headless`; `vmtk` is only the import and CLI compatibility name.

## Quick Check

```bash
python - <<'PY'
import vtk
import vmtk
from vmtk import vtkvmtk

assert vtk.vtkVersion.GetVTKVersion().startswith("9.5.")
assert hasattr(vtkvmtk, "vtkvmtkPolyDataCenterlines")
print("vmtk:", vmtk.__file__)
print("vtkvmtk OK")
PY

vmtk --help
vmtkimagereader --help
```

If you installed from a checkout with test dependencies:

```bash
python -m pytest -q tests/test_headless_install.py
```

## Python Usage

Basic imports:

```python
import vtk
import vmtk
from vmtk import vtkvmtk

print(vmtk.__file__)
print(vtk.vtkVersion.GetVTKVersion())
print(vtkvmtk.vtkvmtkPolyDataCenterlines)
```

Run a VMTK script class on in-memory VTK image data:

```python
import vtk
import vmtk.vmtkimageshiftscale as imageshiftscale

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
print(output.GetTuple1(0), output.GetTuple1(8))
```

Run surface processing on generated VTK polydata:

```python
import vtk
import vmtk.vmtksurfacemassproperties as massproperties

source = vtk.vtkSphereSource()
source.SetRadius(2.0)
source.SetThetaResolution(64)
source.SetPhiResolution(32)
source.Update()

props = massproperties.vmtkSurfaceMassProperties()
props.Surface = source.GetOutput()
props.Execute()

print(props.SurfaceArea, props.Volume, props.ShapeIndex)
```

## CLI Usage

Use non-interactive commands and pipelines. Avoid viewer/renderer stages in
headless environments.

Examples:

```bash
vmtksurfacereader -ifile input.vtp \
  --pipe vmtksurfacesmoothing -iterations 30 -passband 0.1 \
  --pipe vmtksurfacewriter -ofile smoothed.vtp
```

```bash
vmtkimagereader -ifile image.vti \
  --pipe vmtkmarchingcubes -l 500 \
  --pipe vmtksurfacewriter -ofile surface.vtp
```

Centerline workflows are available, but choose non-interactive seed selectors
and do not pipe into viewers:

```bash
vmtkcenterlines -ifile surface.vtp -ofile centerlines.vtp \
  -seedselector openprofiles
```

## Build From Source

The source build is a normal PEP 517 build:

```bash
python -m pip install "vmtk-headless @ git+https://github.com/quantumxiaol/vmtk-headless.git"
```

Local development with `uv`:

```bash
uv sync --extra test
uv run python tools/smoke_test_install.py
uv run pytest -q tests/test_headless_install.py
```

Build a wheel locally:

```bash
uv build --wheel
```

The build configuration is in `pyproject.toml`:

- Build backend: `scikit-build-core`.
- CMake minimum from scikit-build: `>=3.21`.
- Runtime dependency for source installs: `vtk==9.5.0`.
- macOS build isolation dependency: `vtk-sdk==9.5.0`.
- Linux build isolation dependency: `vtk==9.5.0`.
- Default CMake options:
  - `VMTK_USE_SUPERBUILD=OFF`
  - `USE_SYSTEM_VTK=ON`
  - `VMTK_ENABLE_SEGMENTATION=OFF`
  - `VMTK_USE_RENDERING=OFF`
  - `VMTK_BUILD_TETGEN=OFF`
  - `VMTK_CONTRIB_SCRIPTS=ON`
  - `VTK_VMTK_CONTRIB=OFF`
  - `VMTK_SCRIPTS_ENABLED=ON`
  - `VTK_VMTK_WRAP_PYTHON=ON`
  - `VTK_WRAP_PYTHON=ON`
  - `BUILD_SHARED_LIBS=ON`
  - `VMTK_BUILD_TESTING=OFF`

### Custom VTK

If you intentionally build against a custom VTK SDK, pass `VTK_DIR`:

```bash
python -m pip install \
  "vmtk-headless @ git+https://github.com/quantumxiaol/vmtk-headless.git" \
  --config-settings=cmake.define.VTK_DIR=/path/to/vtk/lib/cmake/vtk-9.5
```

Linux source builds can auto-stage the official VTK wheel SDK through
`tools/prepare_linux_vtk_sdk.py` when `VTK_DIR` is not provided. This is needed
because the PyPI `vtk` runtime wheel does not ship `vtk-config.cmake`.

## Wheel Build Pipeline

GitHub Actions builds CPython 3.10 wheels with `cibuildwheel` for:

- `ubuntu-22.04` x86_64
- `ubuntu-24.04` x86_64
- `macos-14` arm64

The wheel workflow:

1. Installs/builds against VTK `9.5.0`.
2. On Linux, stages the matching official VTK wheel SDK.
3. Builds VMTK with the headless CMake options above.
4. Vendors the VTK Python/runtime payload under `vmtk/.vtk`.
5. Repairs native libraries with `auditwheel` on Linux or `delocate` on macOS.
6. Runs an isolated import test that verifies `import vmtk`, `from vmtk import
   vtkvmtk`, and vendored `vtk` loading.

For source installs, `vtk==9.5.0` remains the runtime dependency. For wheels
processed by the CI repair scripts, VTK is bundled under `vmtk/.vtk` to keep the
VMTK native extensions aligned with the VTK runtime they were built against.

## Tests

Fast package smoke tests:

```bash
uv run python tools/smoke_test_install.py
uv run pytest -q tests/test_headless_install.py
```

CI uses two levels of tests:

- `Test pip install git+` runs on push and pull request. It installs the package
  from `git+file://`, runs `tools/smoke_test_install.py`, and runs
  `tests/test_headless_install.py`.
- `Test headless data subset` is a heavier workflow that fetches the upstream
  `tests/vmtk-test-data` submodule, installs the current checkout, and runs a
  curated headless-compatible data subset. It can be started manually from
  GitHub Actions when you want a deeper data-path check.

The full upstream pytest tree is still present, but it is not the default
release gate for this fork. Many upstream tests require the large
`tests/vmtk-test-data` submodule or disabled GUI/segmentation features.

## Upstream VMTK

VMTK is a collection of libraries and tools for 3D reconstruction, geometric
analysis, mesh generation, centerline extraction, and surface data analysis for
image-based modeling of blood vessels.

Upstream resources:

- Website: https://www.vmtk.org
- Documentation: https://www.vmtk.org/documentation/
- Tutorials: https://www.vmtk.org/tutorials/
- Upstream repository: https://github.com/vmtk/vmtk
- DOI: https://doi.org/10.21105/joss.00745

This package is not the official VMTK distribution. It is a headless packaging
fork for Python package managers and automated environments.
