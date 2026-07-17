"""
OPC-Agents Version Management Module

This is the Single Source of Truth (SSOT) for version numbers.
All other version references should import from here.
"""

__version__ = "0.3.32"
__version_info__ = (0, 3, 32)


def get_version() -> str:
    """Get version string

    Returns:
        str: Version number in "major.minor.patch[.postN]" format
    """
    return __version__


def get_version_info() -> tuple:
    """Get version info tuple

    Returns:
        tuple: Version info tuple (major, minor, patch)
    """
    return __version_info__


def get_version_string() -> str:
    """Get full version string (including project name)

    Returns:
        str: Full version string, e.g. "OPC-Agents v{__version__}"
    """
    return f"OPC-Agents v{__version__}"
