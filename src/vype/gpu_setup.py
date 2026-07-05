"""Post-install GPU enablement for the frozen (installer) build.

The installer ships CPU onnxruntime to stay small. `vype.exe --setup-gpu`
downloads the CUDA runtime as pinned wheels straight from PyPI (~1.5 GB),
extracts only the DLLs into the install directory, and the app activates them
at startup. No pip, no system CUDA install — just the NVIDIA driver.

Version pinning is load-bearing: the GPU onnxruntime build must be the EXACT
version of the bundled CPU one (its python shims are shared), and the 1.22
line is the last CUDA-12 build published with Windows wheels.
"""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

ORT_VERSION = "1.22.0"  # must match the onnxruntime pinned in the build venv

# (pypi project, exact version, wheel-member prefix filter)
# nvrtc + nvjitlink are load-time dependencies of cublas/cudnn — without them
# the GPU onnxruntime pybind module fails to import.
PACKAGES: list[tuple[str, str, str]] = [
    ("onnxruntime-gpu", ORT_VERSION, "onnxruntime/capi/"),
    ("nvidia-cuda-runtime-cu12", "12.9.79", "nvidia/"),
    ("nvidia-cuda-nvrtc-cu12", "12.9.86", "nvidia/"),
    ("nvidia-nvjitlink-cu12", "12.9.86", "nvidia/"),
    ("nvidia-cublas-cu12", "12.9.2.10", "nvidia/"),
    ("nvidia-cufft-cu12", "11.4.1.4", "nvidia/"),
    ("nvidia-cudnn-cu12", "9.24.0.43", "nvidia/"),
]

# core CUDA DLLs must be pinned into the process in dependency order before
# onnxruntime loads its CUDA provider; the rest resolve from the directory
_LOAD_ORDER = (
    "cudart", "nvjitlink", "nvrtc", "cublaslt", "cublas", "cufft", "cudnn64", "cudnn_",
)


def _py_tag() -> str:
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


def pick_wheel_url(pypi_json: dict, version: str, py_tag: str | None = None) -> str:
    """Select the wheel for this platform AND this Python.

    ABI-tagged wheels (onnxruntime's cpXY) must match the running interpreter —
    a cp313 pyd in a cp311 bundle fails to load (links python313.dll).
    Pure-python wheels (py3-none) match any interpreter.
    """
    py_tag = py_tag or _py_tag()
    files = pypi_json.get("releases", {}).get(version) or pypi_json.get("urls", [])
    candidates = [
        f["url"]
        for f in files
        if f.get("filename", "").endswith(".whl")
        and ("win_amd64" in f["filename"] or "py3-none-any" in f["filename"])
        and (f"{py_tag}-" in f["filename"] or "py3-none" in f["filename"])
    ]
    if not candidates:
        raise RuntimeError(f"no Windows {py_tag} wheel found for version {version}")
    # prefer platform-specific over universal
    candidates.sort(key=lambda u: ("win_amd64" not in u))
    return candidates[0]


def wanted_members(names: list[str], prefix: str) -> list[str]:
    """Filter wheel members to the DLL/PYD payload we extract."""
    return [
        n
        for n in names
        if n.startswith(prefix) and n.lower().endswith((".dll", ".pyd"))
    ]


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    raise RuntimeError("GPU setup targets the installed (frozen) build; "
                       "use pip in a dev environment instead")


def _internal_dir() -> Path:
    return app_root() / "_internal"


def _nvidia_dir() -> Path:
    return _internal_dir() / "nvidia_dlls"


def _marker() -> Path:
    return _nvidia_dir() / ".installed"


def is_installed() -> bool:
    try:
        return _marker().exists()
    except Exception:
        return False


def install(progress: Callable[[str, float], None]) -> None:
    """Download and install GPU support. progress(status_text, fraction 0..1)."""
    import httpx

    capi_dest = _internal_dir() / "onnxruntime" / "capi"
    nvidia_dest = _nvidia_dir()
    if not capi_dest.exists():
        raise RuntimeError(f"onnxruntime not found at {capi_dest}")
    nvidia_dest.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="vype_gpu_") as tmp:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            for i, (name, version, prefix) in enumerate(PACKAGES):
                base_frac = i / len(PACKAGES)
                progress(f"Fetching {name} {version}…", base_frac)
                meta = client.get(f"https://pypi.org/pypi/{name}/{version}/json").json()
                url = pick_wheel_url(meta, version)

                wheel_path = Path(tmp) / f"{name}.whl"
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length", 0)) or None
                    done = 0
                    with wheel_path.open("wb") as f:
                        for chunk in response.iter_bytes(1 << 20):
                            f.write(chunk)
                            done += len(chunk)
                            if total:
                                frac = base_frac + 0.85 * (done / total) / len(PACKAGES)
                                progress(
                                    f"Downloading {name}  ({done // (1 << 20)} / {total // (1 << 20)} MB)",
                                    frac,
                                )

                progress(f"Installing {name}…", base_frac + 0.9 / len(PACKAGES))
                dest = capi_dest if prefix.startswith("onnxruntime") else nvidia_dest
                with zipfile.ZipFile(wheel_path) as wheel:
                    for member in wanted_members(wheel.namelist(), prefix):
                        target = dest / Path(member).name
                        with wheel.open(member) as src, target.open("wb") as out:
                            shutil.copyfileobj(src, out)
                wheel_path.unlink(missing_ok=True)

    _marker().write_text(f"ort=={ORT_VERSION}\n", encoding="utf-8")
    progress("GPU support installed", 1.0)
    logger.info("GPU support installed to %s", nvidia_dest)


def activate_if_installed() -> bool:
    """Called at app startup, before onnxruntime is imported.

    Pins the CUDA DLLs into the process so the (swapped-in) GPU onnxruntime
    finds them. Returns True when GPU mode is active.
    """
    if not getattr(sys, "frozen", False) or not is_installed():
        return False
    nvidia_dir = _nvidia_dir()
    try:
        os.add_dll_directory(str(nvidia_dir))
    except Exception as exc:
        logger.warning("add_dll_directory failed: %s", exc)

    dlls = sorted(
        nvidia_dir.glob("*.dll"),
        key=lambda p: next(
            (i for i, key in enumerate(_LOAD_ORDER) if key in p.name.lower()),
            len(_LOAD_ORDER),
        ),
    )
    loaded = 0
    for dll in dlls:
        try:
            ctypes.WinDLL(str(dll))
            loaded += 1
        except Exception as exc:
            logger.warning("CUDA DLL preload failed for %s: %s", dll.name, exc)
    logger.info("GPU mode active (%d/%d CUDA DLLs preloaded)", loaded, len(dlls))
    return True
