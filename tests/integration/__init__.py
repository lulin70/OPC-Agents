#!/usr/bin/env python3
"""
OPC-Agents 集成测试套件

测试关键用户旅程和端到端场景
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(scope="session")
def test_config():
    """测试配置"""
    return {
        "base_url": "http://localhost:5009",
        "timeout": 30,
        "max_retries": 3
    }


@pytest.fixture(scope="session")
def opc_manager():
    """创建 OPC Manager 实例"""
    from opc_manager.core import OPCManager
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent.parent / "config.toml.sample"
    manager = OPCManager(config_path=str(config_path))
    return manager


@pytest.fixture(scope="session")
def context_manager(opc_manager):
    """获取上下文管理器"""
    return opc_manager.context_manager


@pytest.fixture(scope="function")
def clean_context(context_manager):
    """清理上下文的 fixture"""
    # 测试前清理
    context_manager.global_context.experiences.clear()
    context_manager.global_context.knowledge.clear()
    
    yield context_manager
    
    # 测试后清理
    context_manager.global_context.experiences.clear()
    context_manager.global_context.knowledge.clear()
