#!/usr/bin/env python3
"""Download and stage the Linux VTK SDK for wheel builds.

The PyPI ``vtk`` runtime wheel does not ship ``vtk-config.cmake``, but VMTK's
native build uses ``find_package(VTK)``. This helper fetches the official VTK
SDK tarball used for wheel builds and places it in a deterministic location so
CI can set ``VTK_DIR`` and ``CMAKE_PREFIX_PATH``.
"""

from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path


SDK_URL = (
    "https://vtk.org/files/wheel-sdks/"
    "vtk-wheel-sdk-9.5.0-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64.tar.xz"
)
ARCHIVE_ROOT = (
    "vtk-wheel-sdk-9.5.0-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64"
)
VTK_CONFIG_REL = Path("vtk-9.5.0.data/headers/cmake/vtk-config.cmake")
DEFAULT_TARGET_ROOT = Path("/tmp/vmtk-vtk-sdk/linux-cp310-x86_64")


def ensure_sdk(target_root: Path) -> None:
    vtk_config = target_root / VTK_CONFIG_REL
    if vtk_config.exists():
        print(f"[linux-vtk-sdk] reuse: {target_root}")
        print(f"[linux-vtk-sdk] vtk-config: {vtk_config}")
        return

    target_root.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="vmtk-vtk-sdk-") as td:
        temp_dir = Path(td)
        archive_path = temp_dir / "vtk-sdk.tar.xz"
        print(f"[linux-vtk-sdk] download: {SDK_URL}")
        urllib.request.urlretrieve(SDK_URL, archive_path)

        with tarfile.open(archive_path, "r:xz") as tar:
            tar.extractall(temp_dir)

        extracted_root = temp_dir / ARCHIVE_ROOT
        if not extracted_root.exists():
            raise RuntimeError(f"Extracted SDK root not found: {extracted_root}")

        if target_root.exists():
            shutil.rmtree(target_root)
        shutil.move(str(extracted_root), str(target_root))

    vtk_config = target_root / VTK_CONFIG_REL
    if not vtk_config.exists():
        raise RuntimeError(f"VTK config missing after extraction: {vtk_config}")

    print(f"[linux-vtk-sdk] ready: {target_root}")
    print(f"[linux-vtk-sdk] vtk-config: {vtk_config}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target-root",
        type=Path,
        default=DEFAULT_TARGET_ROOT,
        help="Extraction target directory for the VTK SDK payload.",
    )
    args = parser.parse_args()
    ensure_sdk(args.target_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
