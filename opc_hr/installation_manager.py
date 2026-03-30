#!/usr/bin/env python3
"""
InstallationManager模块

实现系统安装优化功能，支持依赖管理和系统配置自动调整。
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

class InstallationManager:
    """安装管理器类"""
    
    def __init__(self):
        """初始化安装管理器"""
        self.logger = logging.getLogger('OPC-Agents.InstallationManager')
        self.installation_history = []
        self.dependency_cache = {}
        self.system_config = {}
    
    def install_dependencies(self, dependencies: List[str], upgrade: bool = False) -> Dict[str, Any]:
        """
        安装依赖包
        
        Args:
            dependencies: 依赖包列表
            upgrade: 是否升级依赖
            
        Returns:
            安装结果
        """
        try:
            installation_result = {
                'success': False,
                'installed': [],
                'failed': [],
                'duration': 0,
                'error': None
            }
            
            start_time = datetime.now()
            
            for dependency in dependencies:
                try:
                    # 构建pip命令
                    pip_cmd = [sys.executable, '-m', 'pip', 'install']
                    if upgrade:
                        pip_cmd.append('--upgrade')
                    pip_cmd.append(dependency)
                    
                    # 执行安装
                    subprocess.run(pip_cmd, check=True, capture_output=True, text=True)
                    installation_result['installed'].append(dependency)
                    self.logger.info(f"安装依赖成功: {dependency}")
                except subprocess.CalledProcessError as e:
                    installation_result['failed'].append(dependency)
                    self.logger.error(f"安装依赖失败: {dependency}, 错误: {e.stderr}")
            
            # 计算安装时间
            end_time = datetime.now()
            installation_result['duration'] = (end_time - start_time).total_seconds()
            
            # 检查是否全部成功
            if not installation_result['failed']:
                installation_result['success'] = True
            
            # 记录安装历史
            installation_record = {
                'timestamp': datetime.now().isoformat(),
                'dependencies': dependencies,
                'upgrade': upgrade,
                'result': installation_result
            }
            self.installation_history.append(installation_record)
            
            return installation_result
        except Exception as e:
            self.logger.error(f"安装依赖失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_dependencies(self) -> Dict[str, Any]:
        """
        检查依赖状态
        
        Returns:
            依赖状态
        """
        try:
            # 获取已安装的包
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'list', '--format=json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            installed_packages = json.loads(result.stdout)
            
            # 检查缺失的依赖
            required_dependencies = self._get_required_dependencies()
            missing_dependencies = []
            outdated_dependencies = []
            
            # 检查每个依赖
            for dep in required_dependencies:
                dep_name = dep.split('==')[0] if '==' in dep else dep
                found = False
                
                for pkg in installed_packages:
                    if pkg['name'].lower() == dep_name.lower():
                        found = True
                        # 检查版本
                        if '==' in dep:
                            required_version = dep.split('==')[1]
                            if pkg['version'] != required_version:
                                outdated_dependencies.append(f"{dep_name} (当前版本: {pkg['version']}, 要求版本: {required_version})")
                
                if not found:
                    missing_dependencies.append(dep)
            
            dependency_status = {
                'total_required': len(required_dependencies),
                'missing': missing_dependencies,
                'outdated': outdated_dependencies,
                'installed': [pkg['name'] for pkg in installed_packages]
            }
            
            self.logger.info(f"检查依赖完成，缺失: {len(missing_dependencies)}, 过时: {len(outdated_dependencies)}")
            return dependency_status
        except Exception as e:
            self.logger.error(f"检查依赖失败: {e}")
            return {
                'error': str(e)
            }
    
    def _get_required_dependencies(self) -> List[str]:
        """
        获取系统所需的依赖
        
        Returns:
            依赖列表
        """
        # 从requirements.txt文件获取依赖
        requirements_file = 'requirements.txt'
        dependencies = []
        
        if os.path.exists(requirements_file):
            try:
                with open(requirements_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            dependencies.append(line)
            except Exception as e:
                self.logger.error(f"读取requirements.txt失败: {e}")
        
        # 添加默认依赖
        default_dependencies = [
            'flask',
            'requests',
            'pytest'
        ]
        
        for dep in default_dependencies:
            if dep not in dependencies:
                dependencies.append(dep)
        
        return dependencies
    
    def optimize_installation(self) -> Dict[str, Any]:
        """
        优化系统安装
        
        Returns:
            优化结果
        """
        try:
            optimization_result = {
                'success': False,
                'actions': [],
                'results': {}
            }
            
            # 检查依赖
            self.logger.info("开始优化安装...")
            dependency_status = self.check_dependencies()
            optimization_result['results']['dependency_check'] = dependency_status
            
            # 安装缺失的依赖
            if 'missing' in dependency_status and dependency_status['missing']:
                self.logger.info(f"安装缺失的依赖: {dependency_status['missing']}")
                install_result = self.install_dependencies(dependency_status['missing'])
                optimization_result['actions'].append('安装缺失的依赖')
                optimization_result['results']['install_missing'] = install_result
            
            # 升级过时的依赖
            if 'outdated' in dependency_status and dependency_status['outdated']:
                outdated_packages = [dep.split(' ')[0] for dep in dependency_status['outdated']]
                self.logger.info(f"升级过时的依赖: {outdated_packages}")
                upgrade_result = self.install_dependencies(outdated_packages, upgrade=True)
                optimization_result['actions'].append('升级过时的依赖')
                optimization_result['results']['upgrade_outdated'] = upgrade_result
            
            # 清理缓存
            self._clean_cache()
            optimization_result['actions'].append('清理缓存')
            
            # 检查系统配置
            config_check = self.check_system_config()
            optimization_result['results']['config_check'] = config_check
            
            # 调整系统配置
            if not config_check['valid']:
                config_fix = self.fix_system_config()
                optimization_result['actions'].append('调整系统配置')
                optimization_result['results']['config_fix'] = config_fix
            
            optimization_result['success'] = True
            self.logger.info("安装优化完成")
            return optimization_result
        except Exception as e:
            self.logger.error(f"优化安装失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _clean_cache(self):
        """
        清理缓存
        """
        try:
            # 清理pip缓存
            subprocess.run(
                [sys.executable, '-m', 'pip', 'cache', 'purge'],
                capture_output=True,
                text=True
            )
            self.logger.info("清理pip缓存成功")
        except Exception as e:
            self.logger.error(f"清理缓存失败: {e}")
    
    def check_system_config(self) -> Dict[str, Any]:
        """
        检查系统配置
        
        Returns:
            配置检查结果
        """
        try:
            config_check = {
                'valid': True,
                'issues': [],
                'recommendations': []
            }
            
            # 检查Python版本
            python_version = sys.version_info
            if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
                config_check['valid'] = False
                config_check['issues'].append(f"Python版本过低: {python_version.major}.{python_version.minor}.{python_version.micro}")
                config_check['recommendations'].append("建议升级到Python 3.7或更高版本")
            
            # 检查内存
            try:
                import psutil
                memory = psutil.virtual_memory()
                if memory.available < 1024 * 1024 * 1024:  # 1GB
                    config_check['issues'].append(f"可用内存不足: {memory.available / (1024 * 1024 * 1024):.2f}GB")
                    config_check['recommendations'].append("建议增加系统内存至少2GB")
            except ImportError:
                pass
            
            # 检查磁盘空间
            try:
                import psutil
                disk = psutil.disk_usage('/')
                if disk.free < 10 * 1024 * 1024 * 1024:  # 10GB
                    config_check['issues'].append(f"可用磁盘空间不足: {disk.free / (1024 * 1024 * 1024):.2f}GB")
                    config_check['recommendations'].append("建议清理磁盘空间至少10GB")
            except ImportError:
                pass
            
            # 检查环境变量
            required_env_vars = ['OPC_AGENTS_DIR']
            for var in required_env_vars:
                if var not in os.environ:
                    config_check['issues'].append(f"缺少环境变量: {var}")
                    config_check['recommendations'].append(f"设置环境变量 {var}")
            
            self.logger.info(f"系统配置检查完成，有效: {config_check['valid']}")
            return config_check
        except Exception as e:
            self.logger.error(f"检查系统配置失败: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    def fix_system_config(self) -> Dict[str, Any]:
        """
        修复系统配置
        
        Returns:
            修复结果
        """
        try:
            fix_result = {
                'success': False,
                'fixed': [],
                'failed': []
            }
            
            # 设置必要的环境变量
            if 'OPC_AGENTS_DIR' not in os.environ:
                try:
                    os.environ['OPC_AGENTS_DIR'] = os.getcwd()
                    fix_result['fixed'].append('设置OPC_AGENTS_DIR环境变量')
                    self.logger.info("设置OPC_AGENTS_DIR环境变量成功")
                except Exception as e:
                    fix_result['failed'].append('设置OPC_AGENTS_DIR环境变量')
                    self.logger.error(f"设置环境变量失败: {e}")
            
            # 创建必要的目录
            required_dirs = ['data', 'logs', 'optimization_records', 'optimization_notifications']
            for dir_name in required_dirs:
                if not os.path.exists(dir_name):
                    try:
                        os.makedirs(dir_name, exist_ok=True)
                        fix_result['fixed'].append(f"创建目录: {dir_name}")
                        self.logger.info(f"创建目录成功: {dir_name}")
                    except Exception as e:
                        fix_result['failed'].append(f"创建目录: {dir_name}")
                        self.logger.error(f"创建目录失败: {e}")
            
            # 检查配置文件
            config_files = ['config.toml']
            for config_file in config_files:
                if not os.path.exists(config_file):
                    try:
                        # 创建默认配置文件
                        with open(config_file, 'w', encoding='utf-8') as f:
                            f.write("# OPC-Agents 配置文件\n")
                            f.write("[general]\n")
                            f.write("debug = false\n")
                            f.write("log_level = 'info'\n")
                        fix_result['fixed'].append(f"创建配置文件: {config_file}")
                        self.logger.info(f"创建配置文件成功: {config_file}")
                    except Exception as e:
                        fix_result['failed'].append(f"创建配置文件: {config_file}")
                        self.logger.error(f"创建配置文件失败: {e}")
            
            fix_result['success'] = len(fix_result['failed']) == 0
            self.logger.info("系统配置修复完成")
            return fix_result
        except Exception as e:
            self.logger.error(f"修复系统配置失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_installation_history(self) -> List[Dict[str, Any]]:
        """
        获取安装历史
        
        Returns:
            安装历史列表
        """
        return self.installation_history
    
    def generate_installation_report(self) -> Dict[str, Any]:
        """
        生成安装报告
        
        Returns:
            安装报告
        """
        try:
            # 检查依赖
            dependency_status = self.check_dependencies()
            
            # 检查系统配置
            config_status = self.check_system_config()
            
            # 生成报告
            report = {
                'generated_at': datetime.now().isoformat(),
                'system_info': {
                    'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    'os': sys.platform,
                    'cwd': os.getcwd()
                },
                'dependency_status': dependency_status,
                'config_status': config_status,
                'installation_history': self.installation_history[-5:]  # 最近5条记录
            }
            
            self.logger.info("生成安装报告成功")
            return report
        except Exception as e:
            self.logger.error(f"生成安装报告失败: {e}")
            return {
                'error': str(e)
            }

# 测试代码
if __name__ == "__main__":
    # 初始化日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建InstallationManager实例
    install_manager = InstallationManager()
    
    # 测试检查依赖
    print("测试检查依赖:")
    dependency_status = install_manager.check_dependencies()
    print(f"依赖状态: {dependency_status}")
    
    # 测试安装依赖
    print("\n测试安装依赖:")
    test_dependencies = ['requests']
    install_result = install_manager.install_dependencies(test_dependencies)
    print(f"安装结果: {install_result}")
    
    # 测试检查系统配置
    print("\n测试检查系统配置:")
    config_status = install_manager.check_system_config()
    print(f"配置状态: {config_status}")
    
    # 测试修复系统配置
    print("\n测试修复系统配置:")
    fix_result = install_manager.fix_system_config()
    print(f"修复结果: {fix_result}")
    
    # 测试优化安装
    print("\n测试优化安装:")
    optimization_result = install_manager.optimize_installation()
    print(f"优化结果: {optimization_result}")
    
    # 测试生成安装报告
    print("\n测试生成安装报告:")
    report = install_manager.generate_installation_report()
    print(f"报告生成成功: {report.get('generated_at')}")
    
    print("\nInstallationManager测试完成！")
