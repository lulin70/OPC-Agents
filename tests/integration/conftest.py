#!/usr/bin/env python3
"""
集成测试 fixture 配置

提供所有集成测试共用的 fixture 和配置
"""

import pytest
import shutil
from pathlib import Path
from opc_manager.core import OPCManager
from opc_manager.context_manager import GlobalContext, TaskContext


@pytest.fixture(scope="session")
def test_config():
    """测试配置"""
    return {
        "base_url": "http://localhost:5009",
        "timeout": 30,
        "max_retries": 3,
        "test_db_path": "/tmp/opc_agents_test.db"
    }


@pytest.fixture(scope="session")
def project_root():
    """项目根目录"""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def config_path(project_root):
    """配置文件路径"""
    return project_root / "config.toml.sample"


@pytest.fixture(scope="session")
def opc_manager(config_path):
    """
    创建 OPCManager 实例（会话级）
    
    在整个测试会话中只创建一次，提高测试效率
    """
    manager = OPCManager(config_path=str(config_path))
    return manager


@pytest.fixture(scope="function")
def clean_context(opc_manager):
    """
    清理上下文的 fixture（函数级）
    
    每个测试函数执行前后都会清理上下文，确保测试独立性
    """
    # 测试前清理
    opc_manager.global_context.experiences.clear()
    opc_manager.global_context.knowledge.clear()
    
    # 创建一个简单的包装对象，使测试可以访问 global_context
    class ContextWrapper:
        def __init__(self, global_context):
            self.global_context = global_context
        
        def get_task_context(self):
            """返回一个模拟的 task context"""
            from opc_manager.context_manager import TaskContext
            return TaskContext(task_id="test_task")
    
    wrapper = ContextWrapper(opc_manager.global_context)
    yield wrapper
    
    # 测试后清理
    opc_manager.global_context.experiences.clear()
    opc_manager.global_context.knowledge.clear()


@pytest.fixture(scope="function")
def temp_dir(tmp_path):
    """
    临时目录 fixture
    
    为每个测试创建独立的临时目录，测试结束后自动清理
    """
    temp_directory = tmp_path / "opc_test"
    temp_directory.mkdir(parents=True, exist_ok=True)
    yield temp_directory
    # 自动清理（pytest 的 tmp_path 会自动处理）


@pytest.fixture(scope="session")
def test_database(test_config):
    """
    测试数据库 fixture
    
    创建独立的测试数据库，测试结束后清理
    """
    db_path = Path(test_config["test_db_path"])
    
    # 如果数据库已存在，先备份
    backup_path = None
    if db_path.exists():
        backup_path = db_path.parent / f"{db_path.name}.backup"
        shutil.copy2(db_path, backup_path)
        db_path.unlink()
    
    yield db_path
    
    # 测试结束后恢复或清理
    if backup_path and backup_path.exists():
        if db_path.exists():
            db_path.unlink()
        shutil.move(str(backup_path), str(db_path))


@pytest.fixture(scope="function")
def mock_task_data():
    """
    模拟任务数据 fixture
    
    提供常用的测试任务数据
    """
    return {
        "task_id": "test_task_001",
        "task_name": "测试任务",
        "task_description": "这是一个测试任务",
        "department": "engineering",
        "agent_name": "测试工程师",
        "priority": "normal",
        "status": "pending",
        "deliverables": [],
        "acceptance_criteria": ["功能正常", "性能达标", "无严重缺陷"]
    }


@pytest.fixture(scope="function")
def mock_experience_data():
    """
    模拟经验数据 fixture
    
    提供常用的测试经验数据
    """
    return {
        "task_type": "test_task",
        "task_description": "测试任务描述",
        "success": True,
        "experience_type": "agent_optimization",
        "lessons_learned": ["测试经验 1", "测试经验 2"],
        "best_practices": ["最佳实践 1", "最佳实践 2"],
        "confidence": 0.9,
        "source": "task_completion"
    }


@pytest.fixture(scope="function")
def mock_knowledge_data():
    """
    模拟知识数据 fixture
    
    提供常用的测试知识数据
    """
    return {
        "domain": "test_domain",
        "content": "测试知识内容",
        "keywords": ["测试", "知识", "fixture"],
        "source": "test_source"
    }


@pytest.fixture(scope="function")
def mock_agent_data():
    """
    模拟 Agent 数据 fixture
    
    提供常用的测试 Agent 数据
    """
    return {
        "name": "测试 Agent",
        "role": "测试工程师",
        "department": "engineering",
        "skills": ["单元测试", "集成测试", "性能测试"],
        "status": "idle",
        "current_task": None
    }


# Helper functions for tests
def create_test_experience(task_type="test", success=True, **kwargs):
    """
    辅助函数：创建测试经验对象
    
    用法:
        exp = create_test_experience(
            task_type="web_development",
            lessons_learned=["经验 1"]
        )
    """
    from opc_manager.context_manager import ExperienceItem
    
    data = {
        "task_type": task_type,
        "task_description": kwargs.get("task_description", "测试任务"),
        "success": success,
        "experience_type": kwargs.get("experience_type", "agent_optimization"),
        "lessons_learned": kwargs.get("lessons_learned", []),
        "best_practices": kwargs.get("best_practices", []),
        "confidence": kwargs.get("confidence", 0.9),
        "source": kwargs.get("source", "task_completion")
    }
    
    return ExperienceItem(**data)


def create_test_knowledge(domain="test", **kwargs):
    """
    辅助函数：创建测试知识对象
    
    用法:
        knowledge = create_test_knowledge(
            domain="web_development",
            content="知识内容"
        )
    """
    from opc_manager.context_manager import KnowledgeItem
    
    data = {
        "domain": domain,
        "content": kwargs.get("content", "测试知识"),
        "keywords": kwargs.get("keywords", ["测试"]),
        "source": kwargs.get("source", "test")
    }
    
    return KnowledgeItem(**data)
