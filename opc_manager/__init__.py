#!/usr/bin/env python3
"""
OPC Manager package initialization
"""

from .core import OPCManager
from .log_config import LogConfig

__all__ = ['OPCManager', 'LogConfig']