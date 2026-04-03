"""
ClawHub 集成技能
实现技能包的搜索、下载、安装、更新和卸载功能
"""

import os
import json
import hashlib
import shutil
import zipfile
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


class ClawHubIntegration:
    """
    ClawHub 集成技能
    提供技能包的全生命周期管理
    """
    
    METADATA = {
        'name': 'clawhub_integration',
        'version': '1.0.0',
        'description': 'ClawHub 技能包集成管理，支持搜索/下载/安装/更新/卸载',
        'author': 'OPC-Agents Team',
        'category': 'system',
        'tags': ['clawhub', 'package', 'manager', 'skill'],
        'operations': [
            {
                'name': 'search_packages',
                'description': '搜索 ClawHub 上的技能包',
                'parameters': {
                    'query': {'type': 'str', 'required': True, 'description': '搜索关键词'},
                    'category': {'type': 'str', 'required': False, 'description': '分类过滤'},
                    'limit': {'type': 'int', 'required': False, 'description': '返回数量限制'}
                }
            },
            {
                'name': 'get_package_info',
                'description': '获取技能包详细信息',
                'parameters': {
                    'package_name': {'type': 'str', 'required': True, 'description': '技能包名称'},
                    'version': {'type': 'str', 'required': False, 'description': '版本号'}
                }
            },
            {
                'name': 'download_package',
                'description': '下载技能包',
                'parameters': {
                    'package_name': {'type': 'str', 'required': True, 'description': '技能包名称'},
                    'version': {'type': 'str', 'required': False, 'description': '版本号'},
                    'dest_dir': {'type': 'str', 'required': False, 'description': '下载目录'}
                }
            },
            {
                'name': 'install_package',
                'description': '安装技能包',
                'parameters': {
                    'package_name': {'type': 'str', 'required': True, 'description': '技能包名称'},
                    'version': {'type': 'str', 'required': False, 'description': '版本号'},
                    'force': {'type': 'bool', 'required': False, 'description': '是否强制安装'}
                }
            },
            {
                'name': 'update_package',
                'description': '更新技能包',
                'parameters': {
                    'package_name': {'type': 'str', 'required': True, 'description': '技能包名称'},
                    'to_version': {'type': 'str', 'required': False, 'description': '目标版本号'}
                }
            },
            {
                'name': 'uninstall_package',
                'description': '卸载技能包',
                'parameters': {
                    'package_name': {'type': 'str', 'required': True, 'description': '技能包名称'},
                    'keep_data': {'type': 'bool', 'required': False, 'description': '是否保留数据'}
                }
            },
            {
                'name': 'list_installed_packages',
                'description': '列出已安装的技能包',
                'parameters': {
                    'category': {'type': 'str', 'required': False, 'description': '分类过滤'}
                }
            },
            {
                'name': 'check_updates',
                'description': '检查技能包更新',
                'parameters': {
                    'package_name': {'type': 'str', 'required': False, 'description': '技能包名称，不传则检查所有'}
                }
            }
        ]
    }
    
    # 默认配置
    DEFAULT_CONFIG = {
        'clawhub_api_url': 'https://api.clawhub.io/v1',  # ClawHub API 地址
        'package_install_dir': 'skills/installed',  # 技能包安装目录
        'package_cache_dir': 'skills/cache',  # 技能包缓存目录
        'registry_file': 'skills/installed_packages.json',  # 已安装技能包注册表
        'timeout': 30,  # 网络请求超时时间
        'verify_ssl': True,  # 是否验证 SSL
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化 ClawHub 集成
        
        Args:
            config: 配置字典
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.api_url = self.config['clawhub_api_url']
        self.install_dir = self.config['package_install_dir']
        self.cache_dir = self.config['package_cache_dir']
        self.registry_file = self.config['registry_file']
        
        # 确保目录存在
        self._ensure_directories()
        
        # 加载已安装技能包注册表
        self.installed_packages = self._load_registry()
        
        # 检查 requests 库
        if requests is None:
            print("警告：requests 库未安装，网络功能将不可用")
    
    def execute(self, operation: str, **kwargs) -> Dict:
        """
        执行操作
        
        Args:
            operation: 操作类型
            **kwargs: 操作参数
            
        Returns:
            操作结果
        """
        operations = {
            'search_packages': self._search_packages,
            'get_package_info': self._get_package_info,
            'download_package': self._download_package,
            'install_package': self._install_package,
            'update_package': self._update_package,
            'uninstall_package': self._uninstall_package,
            'list_installed_packages': self._list_installed_packages,
            'check_updates': self._check_updates,
        }
        
        if operation not in operations:
            return {
                'success': False,
                'error': f'不支持的操作：{operation}',
                'available_operations': list(operations.keys())
            }
        
        try:
            result = operations[operation](**kwargs)
            
            # 只有当结果中没有明确设置 success=False 时才设置为 True
            if 'success' not in result or result.get('success') is not False:
                result['success'] = True
            
            result['timestamp'] = datetime.now().isoformat()
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'operation': operation,
                'timestamp': datetime.now().isoformat()
            }
    
    def _search_packages(self, query: str, category: Optional[str] = None, 
                        limit: int = 20) -> Dict:
        """搜索技能包"""
        if requests is None:
            return {
                'success': False,
                'error': 'requests 库未安装，无法执行搜索'
            }
        
        # 构建搜索参数
        params = {
            'q': query,
            'limit': limit,
            'type': 'skill'
        }
        
        if category:
            params['category'] = category
        
        try:
            # 调用 ClawHub API
            response = requests.get(
                f'{self.api_url}/packages/search',
                params=params,
                timeout=self.config['timeout'],
                verify=self.config['verify_ssl']
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'query': query,
                'total': data.get('total', 0),
                'packages': data.get('packages', []),
                'search_time_ms': data.get('search_time_ms', 0)
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'搜索失败：{str(e)}'
            }
    
    def _get_package_info(self, package_name: str, 
                         version: Optional[str] = None) -> Dict:
        """获取技能包详细信息"""
        if requests is None:
            return {
                'success': False,
                'error': 'requests 库未安装，无法获取信息'
            }
        
        try:
            # 构建 API URL
            if version:
                url = f'{self.api_url}/packages/{package_name}/{version}'
            else:
                url = f'{self.api_url}/packages/{package_name}'
            
            response = requests.get(
                url,
                timeout=self.config['timeout'],
                verify=self.config['verify_ssl']
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'package': data,
                'name': data.get('name'),
                'version': data.get('version'),
                'description': data.get('description'),
                'author': data.get('author'),
                'category': data.get('category'),
                'download_count': data.get('download_count', 0),
                'rating': data.get('rating', 0.0)
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'获取信息失败：{str(e)}'
            }
    
    def _download_package(self, package_name: str, 
                         version: Optional[str] = None,
                         dest_dir: Optional[str] = None) -> Dict:
        """下载技能包"""
        if requests is None:
            return {
                'success': False,
                'error': 'requests 库未安装，无法下载'
            }
        
        # 确定下载目录
        if dest_dir is None:
            dest_dir = self.cache_dir
        else:
            dest_dir = Path(dest_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 获取下载链接
            if version:
                url = f'{self.api_url}/packages/{package_name}/{version}/download'
            else:
                url = f'{self.api_url}/packages/{package_name}/download'
            
            # 下载文件
            response = requests.get(
                url,
                stream=True,
                timeout=self.config['timeout'],
                verify=self.config['verify_ssl']
            )
            response.raise_for_status()
            
            # 保存文件
            filename = f'{package_name}-{version or "latest"}.zip'
            filepath = Path(dest_dir) / filename
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            # 验证文件完整性（如果有 checksum）
            checksum = response.headers.get('X-Checksum-SHA256')
            if checksum:
                file_checksum = self._calculate_file_hash(filepath)
                if file_checksum != checksum:
                    return {
                        'success': False,
                        'error': '文件完整性验证失败'
                    }
            
            return {
                'package_name': package_name,
                'version': version or 'latest',
                'filepath': str(filepath),
                'size': downloaded,
                'checksum_verified': checksum is not None
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'下载失败：{str(e)}'
            }
    
    def _install_package(self, package_name: str, 
                        version: Optional[str] = None,
                        force: bool = False) -> Dict:
        """安装技能包"""
        # 检查是否已安装
        if package_name in self.installed_packages and not force:
            installed_version = self.installed_packages[package_name].get('version')
            if version is None or version == installed_version:
                return {
                    'success': False,
                    'error': f'技能包 {package_name} 已安装（版本：{installed_version}），使用 force=True 强制安装'
                }
        
        # 下载技能包
        download_result = self._download_package(package_name, version)
        if not download_result.get('success', True):
            return download_result
        
        package_file = Path(download_result['filepath'])
        
        try:
            # 解压技能包
            extract_dir = Path(self.install_dir) / package_name
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(package_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 读取技能包元数据
            metadata_file = extract_dir / 'metadata.json'
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            else:
                metadata = {
                    'name': package_name,
                    'version': version or 'unknown'
                }
            
            # 注册已安装的技能包
            self.installed_packages[package_name] = {
                'name': package_name,
                'version': metadata.get('version', version or 'unknown'),
                'install_date': datetime.now().isoformat(),
                'install_path': str(extract_dir),
                'metadata': metadata,
                'enabled': True
            }
            
            # 保存注册表
            self._save_registry()
            
            # 清理缓存文件
            package_file.unlink()
            
            return {
                'success': True,
                'package_name': package_name,
                'version': metadata.get('version', version or 'unknown'),
                'install_path': str(extract_dir),
                'message': f'技能包 {package_name} 安装成功'
            }
            
        except Exception as e:
            # 安装失败，清理目录
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            
            return {
                'success': False,
                'error': f'安装失败：{str(e)}'
            }
    
    def _update_package(self, package_name: str, 
                       to_version: Optional[str] = None) -> Dict:
        """更新技能包"""
        # 检查是否已安装
        if package_name not in self.installed_packages:
            return {
                'success': False,
                'error': f'技能包 {package_name} 未安装'
            }
        
        current_version = self.installed_packages[package_name].get('version')
        
        # 获取最新版本信息
        package_info = self._get_package_info(package_name)
        if not package_info.get('success', True):
            return package_info
        
        latest_version = package_info.get('version')
        
        # 确定目标版本
        if to_version is None:
            target_version = latest_version
        else:
            target_version = to_version
        
        # 检查是否需要更新
        if target_version == current_version:
            return {
                'success': True,
                'message': f'技能包 {package_name} 已是最新版本（{current_version}）',
                'current_version': current_version,
                'updated': False
            }
        
        # 执行安装（会覆盖旧版本）
        install_result = self._install_package(package_name, target_version, force=True)
        
        if install_result.get('success'):
            return {
                'success': True,
                'package_name': package_name,
                'from_version': current_version,
                'to_version': target_version,
                'message': f'技能包 {package_name} 已从 {current_version} 更新到 {target_version}'
            }
        else:
            return install_result
    
    def _uninstall_package(self, package_name: str, 
                          keep_data: bool = False) -> Dict:
        """卸载技能包"""
        # 检查是否已安装
        if package_name not in self.installed_packages:
            return {
                'success': False,
                'error': f'技能包 {package_name} 未安装'
            }
        
        install_info = self.installed_packages[package_name]
        install_path = Path(install_info.get('install_path', ''))
        
        try:
            # 删除安装目录
            if install_path.exists():
                if keep_data:
                    # 保留数据文件，只删除代码
                    for item in install_path.iterdir():
                        if item.name not in ['data', 'config']:
                            if item.is_file():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
                else:
                    shutil.rmtree(install_path)
            
            # 从注册表中移除
            del self.installed_packages[package_name]
            self._save_registry()
            
            return {
                'success': True,
                'package_name': package_name,
                'message': f'技能包 {package_name} 已卸载'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'卸载失败：{str(e)}'
            }
    
    def _list_installed_packages(self, 
                                 category: Optional[str] = None) -> Dict:
        """列出已安装的技能包"""
        packages = list(self.installed_packages.values())
        
        # 按分类过滤
        if category:
            packages = [
                p for p in packages 
                if p.get('metadata', {}).get('category') == category
            ]
        
        return {
            'total': len(packages),
            'packages': packages,
            'category': category
        }
    
    def _check_updates(self, 
                      package_name: Optional[str] = None) -> Dict:
        """检查技能包更新"""
        updates_available = []
        
        # 确定要检查的技能包
        if package_name:
            if package_name not in self.installed_packages:
                return {
                    'success': False,
                    'error': f'技能包 {package_name} 未安装'
                }
            packages_to_check = {package_name: self.installed_packages[package_name]}
        else:
            packages_to_check = self.installed_packages
        
        # 检查每个技能包
        for name, info in packages_to_check.items():
            current_version = info.get('version')
            
            # 获取最新版本信息
            package_info = self._get_package_info(name)
            if package_info.get('success', True):
                latest_version = package_info.get('version')
                
                # 比较版本
                if latest_version != current_version:
                    updates_available.append({
                        'package_name': name,
                        'current_version': current_version,
                        'latest_version': latest_version,
                        'has_update': True
                    })
        
        return {
            'total_checked': len(packages_to_check),
            'updates_available': len(updates_available),
            'updates': updates_available
        }
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        Path(self.install_dir).mkdir(parents=True, exist_ok=True)
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        
        # 确保 registry 文件的父目录存在
        Path(self.registry_file).parent.mkdir(parents=True, exist_ok=True)
    
    def _load_registry(self) -> Dict:
        """加载已安装技能包注册表"""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_registry(self):
        """保存已安装技能包注册表"""
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(self.installed_packages, f, indent=2, ensure_ascii=False)
    
    def _calculate_file_hash(self, filepath: Path) -> str:
        """计算文件 SHA256 哈希"""
        sha256_hash = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()


# 测试代码
if __name__ == '__main__':
    print("ClawHub 集成技能")
    print("=" * 60)
    
    # 创建实例
    clawhub = ClawHubIntegration()
    
    # 列出已安装的技能包
    print("\n[测试] 列出已安装的技能包")
    result = clawhub.execute('list_installed_packages')
    print(f"已安装技能包数量：{result.get('total', 0)}")
    
    # 检查更新
    print("\n[测试] 检查更新")
    result = clawhub.execute('check_updates')
    print(f"检查的技能包数：{result.get('total_checked', 0)}")
    print(f"可更新的技能包数：{result.get('updates_available', 0)}")
    
    print("\n" + "=" * 60)
    print("注意：实际使用需要配置 ClawHub API 地址和网络连接")
