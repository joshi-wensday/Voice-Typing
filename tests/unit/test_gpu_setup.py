"""GPU setup: wheel selection and payload filtering (pure logic)."""

import pytest

from vype.gpu_setup import ORT_VERSION, PACKAGES, pick_wheel_url, wanted_members


def test_pick_wheel_prefers_win_amd64():
    meta = {
        "urls": [
            {"filename": "pkg-1.0-py3-none-manylinux_x86_64.whl", "url": "http://x/linux"},
            {"filename": "pkg-1.0-py3-none-win_amd64.whl", "url": "http://x/win"},
            {"filename": "pkg-1.0.tar.gz", "url": "http://x/sdist"},
        ]
    }
    assert pick_wheel_url(meta, "1.0") == "http://x/win"


def test_pick_wheel_accepts_universal():
    meta = {"urls": [{"filename": "pkg-1.0-py3-none-any.whl", "url": "http://x/any"}]}
    assert pick_wheel_url(meta, "1.0") == "http://x/any"


def test_pick_wheel_from_releases_shape():
    meta = {
        "releases": {
            "2.0": [{"filename": "pkg-2.0-cp311-win_amd64.whl", "url": "http://x/w2"}]
        }
    }
    assert pick_wheel_url(meta, "2.0") == "http://x/w2"


def test_pick_wheel_no_windows_build_raises():
    meta = {"urls": [{"filename": "pkg-1.0-py3-none-manylinux_x86_64.whl", "url": "http://x"}]}
    with pytest.raises(RuntimeError, match="no Windows wheel"):
        pick_wheel_url(meta, "1.0")


def test_wanted_members_filters_dlls_under_prefix():
    names = [
        "onnxruntime/capi/onnxruntime_pybind11_state.pyd",
        "onnxruntime/capi/onnxruntime_providers_cuda.dll",
        "onnxruntime/capi/_ld_preload.py",
        "onnxruntime/__init__.py",
        "onnxruntime_gpu-1.22.0.dist-info/METADATA",
    ]
    got = wanted_members(names, "onnxruntime/capi/")
    assert got == [
        "onnxruntime/capi/onnxruntime_pybind11_state.pyd",
        "onnxruntime/capi/onnxruntime_providers_cuda.dll",
    ]


def test_wanted_members_nvidia_bin_layout():
    names = [
        "nvidia/cudnn/bin/cudnn64_9.dll",
        "nvidia/cudnn/lib/x64/cudnn.lib",
        "nvidia/cudnn/include/cudnn.h",
        "nvidia_cudnn_cu12-9.24.0.43.dist-info/RECORD",
    ]
    assert wanted_members(names, "nvidia/") == ["nvidia/cudnn/bin/cudnn64_9.dll"]


def test_onnxruntime_gpu_pin_matches_bundled_cpu_version():
    """The GPU swap only works when versions are identical — guard the pin."""
    gpu_pin = next(v for name, v, _ in PACKAGES if name == "onnxruntime-gpu")
    assert gpu_pin == ORT_VERSION
