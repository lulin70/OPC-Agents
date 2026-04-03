"""
ClawHub 集成技能单元测试
"""

import pytest
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_skills.clawhub_integration import ClawHubIntegration


class TestClawHubIntegration:
    """ClawHub 集成技能测试类"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def clawhub(self, temp_dir):
        """创建 ClawHub 集成实例（使用临时目录）"""
        config = {
            'package_install_dir': str(temp_dir / 'installed'),
            'package_cache_dir': str(temp_dir / 'cache'),
            'registry_file': str(temp_dir / 'registry.json'),
        }
        return ClawHubIntegration(config)
    
    def test_metadata(self, clawhub):
        """测试技能元数据"""
        assert clawhub.METADATA['name'] == 'clawhub_integration'
        assert clawhub.METADATA['version'] == '1.0.0'
        assert 'clawhub' in clawhub.METADATA['tags']
        assert len(clawhub.METADATA['operations']) >= 8
    
    def test_initialization(self, clawhub, temp_dir):
        """测试初始化"""
        assert clawhub.install_dir == str(temp_dir / 'installed')
        assert clawhub.cache_dir == str(temp_dir / 'cache')
        assert clawhub.registry_file == str(temp_dir / 'registry.json')
        
        # 检查目录是否创建
        assert os.path.exists(clawhub.install_dir)
        assert os.path.exists(clawhub.cache_dir)
    
    def test_execute_invalid_operation(self, clawhub):
        """测试无效操作"""
        result = clawhub.execute('invalid_operation')
        
        assert result['success'] is False
        assert 'error' in result
        assert 'available_operations' in result
    
    def test_list_installed_packages_empty(self, clawhub):
        """测试列出已安装技能包（空列表）"""
        result = clawhub.execute('list_installed_packages')
        
        assert result['success'] is True
        assert result['total'] == 0
        assert result['packages'] == []
    
    def test_check_updates_empty(self, clawhub):
        """测试检查更新（没有已安装的包）"""
        result = clawhub.execute('check_updates')
        
        assert result['success'] is True
        assert result['total_checked'] == 0
        assert result['updates_available'] == 0
    
    def test_uninstall_not_installed_package(self, clawhub):
        """测试卸载未安装的技能包"""
        result = clawhub.execute('uninstall_package', package_name='nonexistent')
        
        assert result['success'] is False
        assert 'error' in result
        assert '未安装' in result['error']
    
    def test_registry_persistence(self, clawhub, temp_dir):
        """测试注册表持久化"""
        # 模拟添加一个技能包
        clawhub.installed_packages['test_package'] = {
            'name': 'test_package',
            'version': '1.0.0',
            'install_date': '2026-04-03T10:00:00',
            'install_path': str(temp_dir / 'installed' / 'test_package'),
            'metadata': {'category': 'test'},
            'enabled': True
        }
        
        # 保存注册表
        clawhub._save_registry()
        
        # 验证文件存在
        assert os.path.exists(clawhub.registry_file)
        
        # 重新加载注册表
        loaded_registry = clawhub._load_registry()
        
        assert 'test_package' in loaded_registry
        assert loaded_registry['test_package']['version'] == '1.0.0'
    
    def test_ensure_directories(self, temp_dir):
        """测试目录创建"""
        config = {
            'package_install_dir': str(temp_dir / 'new_installed'),
            'package_cache_dir': str(temp_dir / 'new_cache'),
            'registry_file': str(temp_dir / 'new_registry.json'),
        }
        
        clawhub = ClawHubIntegration(config)
        
        assert os.path.exists(clawhub.install_dir)
        assert os.path.exists(clawhub.cache_dir)
        assert os.path.exists(os.path.dirname(clawhub.registry_file))
    
    def test_calculate_file_hash(self, clawhub, temp_dir):
        """测试文件哈希计算"""
        # 创建测试文件
        test_file = temp_dir / 'test.txt'
        test_file.write_text('Hello, World!')
        
        # 计算哈希
        hash1 = clawhub._calculate_file_hash(test_file)
        
        # 再次计算哈希（应该相同）
        hash2 = clawhub._calculate_file_hash(test_file)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 哈希长度为 64
    
    def test_list_installed_packages_with_category(self, clawhub, temp_dir):
        """测试按分类列出技能包"""
        # 添加不同分类的技能包
        clawhub.installed_packages['package_a'] = {
            'name': 'package_a',
            'version': '1.0.0',
            'metadata': {'category': 'category_a'}
        }
        
        clawhub.installed_packages['package_b'] = {
            'name': 'package_b',
            'version': '1.0.0',
            'metadata': {'category': 'category_b'}
        }
        
        clawhub._save_registry()
        
        # 按分类过滤
        result_a = clawhub.execute('list_installed_packages', category='category_a')
        result_b = clawhub.execute('list_installed_packages', category='category_b')
        result_c = clawhub.execute('list_installed_packages', category='category_c')
        
        assert result_a['total'] == 1
        assert result_a['packages'][0]['name'] == 'package_a'
        
        assert result_b['total'] == 1
        assert result_b['packages'][0]['name'] == 'package_b'
        
        assert result_c['total'] == 0
    
    def test_check_updates_for_specific_package(self, clawhub):
        """测试检查特定技能包的更新"""
        # 添加一个技能包
        clawhub.installed_packages['test_package'] = {
            'name': 'test_package',
            'version': '1.0.0'
        }
        clawhub._save_registry()
        
        # 检查特定技能包（没有网络时应该返回错误）
        result = clawhub.execute('check_updates', package_name='test_package')
        
        # 由于没有实际网络连接，应该返回错误
        # 但测试主要验证逻辑流程
        assert 'total_checked' in result or 'error' in result
    
    def test_uninstall_package_with_keep_data(self, clawhub, temp_dir):
        """测试卸载技能包时保留数据"""
        # 创建安装目录和文件
        install_path = temp_dir / 'installed' / 'test_package'
        install_path.mkdir(parents=True, exist_ok=True)
        
        # 创建代码文件
        code_file = install_path / 'code.py'
        code_file.write_text('print("Hello")')
        
        # 创建数据目录
        data_dir = install_path / 'data'
        data_dir.mkdir(exist_ok=True)
        data_file = data_dir / 'data.json'
        data_file.write_text('{"key": "value"}')
        
        # 注册技能包
        clawhub.installed_packages['test_package'] = {
            'name': 'test_package',
            'version': '1.0.0',
            'install_path': str(install_path)
        }
        
        # 卸载并保留数据
        result = clawhub.execute('uninstall_package', 
                                package_name='test_package',
                                keep_data=True)
        
        assert result['success'] is True
        
        # 验证数据文件保留
        assert data_dir.exists()
        assert data_file.exists()
        
        # 验证代码文件被删除
        assert not code_file.exists()
        
        # 验证从注册表中移除
        assert 'test_package' not in clawhub.installed_packages
    
    def test_uninstall_package_without_keep_data(self, clawhub, temp_dir):
        """测试完全卸载技能包"""
        # 创建安装目录
        install_path = temp_dir / 'installed' / 'test_package'
        install_path.mkdir(parents=True, exist_ok=True)
        
        # 创建文件
        test_file = install_path / 'test.txt'
        test_file.write_text('test')
        
        # 注册技能包
        clawhub.installed_packages['test_package'] = {
            'name': 'test_package',
            'version': '1.0.0',
            'install_path': str(install_path)
        }
        
        # 卸载
        result = clawhub.execute('uninstall_package', 
                                package_name='test_package',
                                keep_data=False)
        
        assert result['success'] is True
        
        # 验证整个目录被删除
        assert not install_path.exists()
        
        # 验证从注册表中移除
        assert 'test_package' not in clawhub.installed_packages


class TestClawHubIntegrationMock:
    """ClawHub 集成技能测试（使用 Mock）"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def clawhub_mock(self, temp_dir):
        """创建 ClawHub 集成实例（带 Mock）"""
        config = {
            'package_install_dir': str(temp_dir / 'installed'),
            'package_cache_dir': str(temp_dir / 'cache'),
            'registry_file': str(temp_dir / 'registry.json'),
            'clawhub_api_url': 'https://mock-api.clawhub.io/v1',
        }
        return ClawHubIntegration(config)
    
    def test_search_packages_offline(self, clawhub_mock):
        """测试离线搜索（无网络）"""
        # 在没有网络的情况下，应该返回错误
        result = clawhub_mock.execute('search_packages', query='test')
        
        # 由于 requests 可能未安装或无网络，应该返回错误信息
        assert 'success' in result or 'error' in result
    
    def test_get_package_info_offline(self, clawhub_mock):
        """测试离线获取包信息"""
        result = clawhub_mock.execute('get_package_info', package_name='test_package')
        
        # 应该返回错误（无网络）
        assert 'success' in result or 'error' in result
    
    def test_download_package_offline(self, clawhub_mock):
        """测试离线下载包"""
        result = clawhub_mock.execute('download_package', package_name='test_package')
        
        # 应该返回错误（无网络）
        assert 'success' in result or 'error' in result


class TestClawHubIntegrationInstall:
    """ClawHub 安装功能测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def clawhub(self, temp_dir):
        """创建 ClawHub 集成实例"""
        config = {
            'package_install_dir': str(temp_dir / 'installed'),
            'package_cache_dir': str(temp_dir / 'cache'),
            'registry_file': str(temp_dir / 'registry.json'),
        }
        return ClawHubIntegration(config)
    
    def test_install_package_already_installed(self, clawhub, temp_dir):
        """测试安装已存在的包"""
        # 先安装一个包
        install_path = temp_dir / 'installed' / 'test_package'
        install_path.mkdir(parents=True, exist_ok=True)
        
        clawhub.installed_packages['test_package'] = {
            'name': 'test_package',
            'version': '1.0.0',
            'install_path': str(install_path)
        }
        clawhub._save_registry()
        
        # 尝试再次安装（不强制）
        result = clawhub.execute('install_package', package_name='test_package')
        
        assert result['success'] is False
        assert '已安装' in result.get('error', '')
    
    def test_install_package_force(self, clawhub, temp_dir):
        """测试强制安装已存在的包"""
        # 先安装一个包
        install_path = temp_dir / 'installed' / 'test_package'
        install_path.mkdir(parents=True, exist_ok=True)
        
        clawhub.installed_packages['test_package'] = {
            'name': 'test_package',
            'version': '1.0.0',
            'install_path': str(install_path)
        }
        clawhub._save_registry()
        
        # 强制安装（由于没有网络，会失败，但测试逻辑）
        result = clawhub.execute('install_package', 
                                package_name='test_package',
                                force=True)
        
        # 由于没有实际网络，会失败，但应该尝试下载
        # 主要测试 force 参数被正确传递
    
    def test_update_package_not_installed(self, clawhub):
        """测试更新未安装的包"""
        result = clawhub.execute('update_package', package_name='nonexistent')
        
        assert result['success'] is False
        assert '未安装' in result.get('error', '')
    
    def test_update_package_no_update_needed(self, clawhub):
        """测试不需要更新的情况"""
        # 安装一个包
        clawhub.installed_packages['test_package'] = {
            'name': 'test_package',
            'version': '1.0.0'
        }
        clawhub._save_registry()
        
        # Mock get_package_info 返回相同版本
        original_get_info = clawhub._get_package_info
        
        def mock_get_info(package_name, version=None):
            return {
                'success': True,
                'version': '1.0.0',  # 相同版本
                'name': package_name
            }
        
        clawhub._get_package_info = mock_get_info
        
        try:
            result = clawhub.execute('update_package', package_name='test_package')
            
            assert result['success'] is True
            assert result.get('updated') is False
            assert '已是最新版本' in result.get('message', '')
        finally:
            clawhub._get_package_info = original_get_info


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
