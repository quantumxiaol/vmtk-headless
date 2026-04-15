#!/usr/bin/env python3
"""Vendor VTK Python payload into a built wheel and strip external vtk metadata.

This script is platform-neutral and is intended to run before wheel repair
(e.g. auditwheel/delocate) so binary dependencies of vendored vtkmodules are
captured by the repair step.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def parse_wheel_python_version(wheel_path: Path) -> tuple[int, int]:
    match = re.search(r"-cp(\d+)-cp\d+-", wheel_path.name)
    if not match:
        raise ValueError(f"Cannot parse Python tag from wheel name: {wheel_path.name}")
    tag = match.group(1)
    if len(tag) < 2:
        raise ValueError(f"Unsupported Python tag: cp{tag}")
    major = int(tag[0])
    minor = int(tag[1:])
    return major, minor


def _find_vtk_sdk_payload(expected_py: tuple[int, int]) -> tuple[Path, Path] | None:
    major, minor = expected_py
    py_tag = f"{major}{minor}"
    wrapping_lib = f"libvtkWrappingPythonCore{major}.{minor}.so"

    candidates: list[Path] = []
    env_root = os.environ.get("VMTK_VTK_SDK_ROOT", "").strip()
    if env_root:
        candidates.append(Path(env_root))
    candidates.append(Path(f"/tmp/vmtk-vtk-sdk/linux-cp{py_tag}-x86_64"))

    for root in candidates:
        if not root.exists():
            continue
        vtk_py = root / "vtk.py"
        vtkmodules_dir = root / "vtkmodules"
        if not vtk_py.is_file() or not vtkmodules_dir.is_dir():
            continue

        lib_roots = sorted(root.glob(f"build/lib.*-cpython-{py_tag}/vtkmodules"))
        for lib_root in lib_roots:
            if (lib_root / wrapping_lib).is_file():
                return root, lib_root.relative_to(root)

    return None


_X11_RUNTIME_LIBS = {
    "libX11.so.6",
    "libXcursor.so.1",
    "libXext.so.6",
    "libXfixes.so.3",
    "libXi.so.6",
    "libXrender.so.1",
    "libXt.so.6",
    "libxcb.so.1",
}


def _iter_linux_elf_binaries(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(".so") or ".so." in name:
            yield path


def _readelf_dynamic(path: Path) -> str:
    try:
        out = subprocess.run(
            ["readelf", "-d", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ""
    if out.returncode != 0:
        return ""
    return out.stdout


def _elf_needed(path: Path) -> set[str]:
    dynamic = _readelf_dynamic(path)
    if not dynamic:
        return set()
    return set(re.findall(r"Shared library: \[(.+?)\]", dynamic))


def _elf_soname(path: Path) -> str:
    dynamic = _readelf_dynamic(path)
    if not dynamic:
        return path.name
    match = re.search(r"Library soname: \[(.+?)\]", dynamic)
    if match:
        return match.group(1)
    return path.name


def _prune_x11_dependent_binaries(bundle_dir: Path) -> list[Path]:
    if not sys.platform.startswith("linux"):
        return []

    binaries = list(_iter_linux_elf_binaries(bundle_dir))
    info: dict[Path, tuple[set[str], str]] = {}
    for binary in binaries:
        info[binary] = (_elf_needed(binary), _elf_soname(binary))

    to_remove: list[Path] = [
        binary
        for binary, (needed, _) in info.items()
        if needed & _X11_RUNTIME_LIBS
    ]
    removed: list[Path] = []
    removed_set: set[Path] = set()
    removed_sonames: set[str] = set()

    while to_remove:
        victim = to_remove.pop()
        if victim in removed_set or not victim.exists():
            continue

        needed, soname = info.get(victim, (set(), victim.name))
        victim.unlink()
        removed.append(victim)
        removed_set.add(victim)
        removed_sonames.add(soname)

        # Remove dependents that now require a pruned soname.
        for candidate, (candidate_needed, _) in info.items():
            if candidate in removed_set:
                continue
            if not candidate.exists():
                continue
            if candidate_needed & removed_sonames:
                to_remove.append(candidate)

    return removed


def vendor_vtk_payload(root: Path, *, expected_py: tuple[int, int]) -> list[Path]:
    if sys.version_info[:2] != expected_py:
        raise RuntimeError(
            "Patch interpreter version does not match wheel tag: "
            f"interpreter={sys.version_info.major}.{sys.version_info.minor}, "
            f"wheel={expected_py[0]}.{expected_py[1]}"
        )

    try:
        import vtk  # type: ignore
        import vtkmodules  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("vtk/vtkmodules not found in build environment") from exc

    vtk_py_src = Path(vtk.__file__).resolve()
    vtkmodules_src = Path(vtkmodules.__file__).resolve().parent

    bundle_dir = root / "vmtk" / ".vtk"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []

    # Prefer SDK payload when available (Linux CI path). This keeps the runtime
    # layout consistent with the libraries VMTK linked against at build time.
    sdk_payload = _find_vtk_sdk_payload(expected_py)
    if sdk_payload is not None:
        sdk_root, sdk_rel_lib_dir = sdk_payload

        vtk_py_dest = bundle_dir / "vtk.py"
        shutil.copy2(sdk_root / "vtk.py", vtk_py_dest)
        copied.append(vtk_py_dest)

        vtkmodules_dest = bundle_dir / "vtkmodules"
        if vtkmodules_dest.exists():
            shutil.rmtree(vtkmodules_dest)
        shutil.copytree(sdk_root / "vtkmodules", vtkmodules_dest)
        copied.append(vtkmodules_dest)

        sdk_lib_dest = bundle_dir / sdk_rel_lib_dir
        if sdk_lib_dest.exists():
            shutil.rmtree(sdk_lib_dest)
        sdk_lib_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(sdk_root / sdk_rel_lib_dir, sdk_lib_dest)
        copied.append(sdk_lib_dest)

        pruned = _prune_x11_dependent_binaries(bundle_dir)
        for path in pruned:
            print(f"[vendor-vtk] pruned x11-dependent binary: {path}")
        return copied

    vtk_py_dest = bundle_dir / "vtk.py"
    shutil.copy2(vtk_py_src, vtk_py_dest)
    copied.append(vtk_py_dest)

    vtkmodules_dest = bundle_dir / "vtkmodules"
    if vtkmodules_dest.exists():
        shutil.rmtree(vtkmodules_dest)
    shutil.copytree(vtkmodules_src, vtkmodules_dest)
    copied.append(vtkmodules_dest)

    # Linux VTK wheels may store shared libs in different companion folders.
    for src in (
        vtk_py_src.parent / "vtk.libs",
        vtk_py_src.parent / "vtkmodules.libs",
        vtkmodules_src / ".libs",
    ):
        if not src.exists():
            continue
        dest = bundle_dir / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        copied.append(dest)

    pruned = _prune_x11_dependent_binaries(bundle_dir)
    for path in pruned:
        print(f"[vendor-vtk] pruned x11-dependent binary: {path}")

    return copied


def strip_vtk_requirement(root: Path) -> int:
    metadata_files = list(root.rglob("*.dist-info/METADATA"))
    if len(metadata_files) != 1:
        raise RuntimeError(f"Expected exactly one METADATA file, found {len(metadata_files)}")

    metadata_path = metadata_files[0]
    lines = metadata_path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    removed = 0
    for line in lines:
        if line.startswith("Requires-Dist: vtk"):
            removed += 1
            continue
        kept.append(line)
    metadata_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return removed


def compute_record_row(file_path: Path, root: Path) -> tuple[str, str, str]:
    rel = file_path.relative_to(root).as_posix()
    data = file_path.read_bytes()
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return rel, f"sha256={digest}", str(len(data))


def rewrite_record(root: Path) -> Path:
    records = list(root.rglob("*.dist-info/RECORD"))
    if len(records) != 1:
        raise RuntimeError(f"Expected exactly one RECORD file, found {len(records)}")

    record_path = records[0]
    record_rel = record_path.relative_to(root).as_posix()

    rows: list[tuple[str, str, str]] = []
    for file_path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = file_path.relative_to(root).as_posix()
        if rel == record_rel:
            continue
        rows.append(compute_record_row(file_path, root))
    rows.append((record_rel, "", ""))

    with record_path.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerows(rows)
    return record_path


def repack_wheel(unpack_dir: Path, wheel_path: Path) -> None:
    tmp_wheel = wheel_path.with_suffix(wheel_path.suffix + ".tmp")
    with ZipFile(tmp_wheel, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(p for p in unpack_dir.rglob("*") if p.is_file()):
            arcname = file_path.relative_to(unpack_dir).as_posix()
            zf.write(file_path, arcname)
    tmp_wheel.replace(wheel_path)


def patch_wheel(wheel_path: Path) -> None:
    major, minor = parse_wheel_python_version(wheel_path)

    with tempfile.TemporaryDirectory() as td:
        unpack_dir = Path(td) / "wheel"
        with ZipFile(wheel_path) as zf:
            zf.extractall(unpack_dir)

        copied = vendor_vtk_payload(unpack_dir, expected_py=(major, minor))
        removed_requirements = strip_vtk_requirement(unpack_dir)
        record_path = rewrite_record(unpack_dir)
        repack_wheel(unpack_dir, wheel_path)

    for path in copied:
        print(f"[vendor-vtk] vendored: {path}")
    print(f"[vendor-vtk] removed metadata vtk requirements: {removed_requirements}")
    print(f"[vendor-vtk] updated RECORD: {record_path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path, help="Path to built wheel")
    args = parser.parse_args()

    wheel_path = args.wheel.resolve()
    if not wheel_path.exists():
        print(f"Wheel not found: {wheel_path}", file=sys.stderr)
        return 1

    patch_wheel(wheel_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
