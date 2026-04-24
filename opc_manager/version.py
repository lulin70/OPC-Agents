"""OPC-Agents 版本管理模块

这是版本号的单一真相来源(SSOT)。
所有其他地方的版本号都应该从这里导入。
"""

__version__ = "0.1.0-beta"
__version_info__ = (0, 1, 0)


def get_version() -> str:
    """获取版本号字符串

    Returns:
        str: 版本号，格式为 "major.minor.patch"
    """
    return __version__


def get_version_info() -> tuple:
    """获取版本信息元组

    Returns:
        tuple: 版本信息元组 (major, minor, patch)
    """
    return __version_info__


def get_version_string() -> str:
    """获取完整版本字符串（包含项目名）

    Returns:
        str: 完整版本字符串，例如 "OPC-Agents v0.1.0"
    """
    return f"OPC-Agents v{__version__}"
