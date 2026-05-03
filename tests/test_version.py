"""版本号一致性测试

确保VERSION文件、requirements.txt和代码中的版本号保持一致。
支持预发布版本格式（如0.1.0-beta）。
"""

import re
import os
import pytest
from pathlib import Path


def test_version_module_exists():
    """测试version模块是否存在"""
    from opc_manager import version

    assert hasattr(version, "__version__")
    assert hasattr(version, "__version_info__")
    assert hasattr(version, "get_version")
    assert hasattr(version, "get_version_info")


def test_version_format():
    """测试版本号格式是否正确（支持预发布标识和post-release）"""
    from opc_manager.version import __version__, __version_info__

    pattern = r"^\d+\.\d+\.\d+((-[a-zA-Z0-9.]+)|(\.post\d+))?$"
    assert re.match(pattern, __version__), f"版本号格式错误: {__version__}"

    base_version = re.split(r"[-.]", __version__)[0] + "." + re.split(r"[-.]", __version__)[1] + "." + re.split(r"[-.]", __version__)[2]
    parts = base_version.split(".")
    assert len(parts) == 3, f"版本号格式错误: {__version__}"
    for part in parts:
        assert part.isdigit(), f"版本号包含非数字: {part}"

    assert isinstance(__version_info__, tuple)
    assert len(__version_info__) >= 3
    assert all(isinstance(x, int) for x in __version_info__[:3])


def test_version_consistency_with_file():
    """测试VERSION文件与代码版本一致"""
    from opc_manager.version import __version__

    version_file = Path(__file__).parent.parent / "VERSION"
    assert version_file.exists(), "VERSION文件不存在"

    with open(version_file) as f:
        file_version = f.read().strip()

    assert (
        file_version == __version__
    ), f"VERSION文件({file_version}) 与代码版本({__version__})不一致"


def test_version_in_requirements():
    """测试requirements.txt包含基础版本号"""
    from opc_manager.version import __version__

    req_file = Path(__file__).parent.parent / "requirements.txt"
    assert req_file.exists(), "requirements.txt文件不存在"

    with open(req_file) as f:
        content = f.read()

    base_version = __version__.split(".post")[0].split("-")[0]
    assert base_version in content, f"requirements.txt 中未找到版本号 {base_version}"


def test_get_version_function():
    """测试get_version()函数"""
    from opc_manager.version import get_version, __version__

    assert get_version() == __version__
    assert isinstance(get_version(), str)


def test_get_version_info_function():
    """测试get_version_info()函数"""
    from opc_manager.version import get_version_info, __version_info__

    assert get_version_info() == __version_info__
    assert isinstance(get_version_info(), tuple)


def test_get_version_string_function():
    """测试get_version_string()函数"""
    from opc_manager.version import get_version_string, __version__

    version_string = get_version_string()
    assert "OPC-Agents" in version_string
    assert __version__ in version_string
    assert version_string == f"OPC-Agents v{__version__}"


def test_version_import_from_package():
    """测试从包级别导入版本"""
    from opc_manager import __version__, get_version

    assert __version__ is not None
    assert callable(get_version)
    assert get_version() == __version__


def test_version_info_matches_version_base():
    """测试version_info与version基础部分匹配"""
    from opc_manager.version import __version__, __version_info__

    base_version = __version__.split(".post")[0].split("-")[0]
    reconstructed = f"{__version_info__[0]}.{__version_info__[1]}.{__version_info__[2]}"

    assert (
        reconstructed == base_version
    ), f"version_info({__version_info__}) 与 version基础部分({base_version}) 不匹配"
