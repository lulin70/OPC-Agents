"""
安全扫描技能
提供代码安全扫描、权限分析、来源信誉评估等功能
"""

import os
import re
import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime


class SecurityScannerSkill:
    """
    安全扫描技能
    提供多维度的安全评估能力
    """
    
    METADATA = {
        'name': 'security_scanner',
        'version': '1.0.0',
        'description': '安全扫描技能，提供代码扫描/权限分析/来源信誉评估',
        'author': 'OPC-Agents Team',
        'category': 'security',
        'tags': ['security', 'scanner', 'analysis', 'permission'],
        'operations': [
            {
                'name': 'scan_code',
                'description': '静态代码安全扫描',
                'parameters': {
                    'code': {'type': 'str', 'required': True, 'description': '待扫描的代码'},
                    'language': {'type': 'str', 'required': False, 'description': '编程语言'},
                    'scan_level': {'type': 'str', 'required': False, 'description': '扫描级别：basic/standard/deep'}
                }
            },
            {
                'name': 'analyze_permissions',
                'description': '权限分析',
                'parameters': {
                    'permissions': {'type': 'list', 'required': True, 'description': '权限列表'},
                    'context': {'type': 'str', 'required': False, 'description': '使用场景'}
                }
            },
            {
                'name': 'evaluate_reputation',
                'description': '来源信誉评估',
                'parameters': {
                    'source': {'type': 'str', 'required': True, 'description': '来源标识（URL/GitHub 仓库等）'},
                    'source_type': {'type': 'str', 'required': False, 'description': '来源类型：github/pypi/npm/url'}
                }
            },
            {
                'name': 'calculate_security_score',
                'description': '计算综合安全评分',
                'parameters': {
                    'scan_results': {'type': 'dict', 'required': True, 'description': '扫描结果'},
                    'permission_results': {'type': 'dict', 'required': False, 'description': '权限分析结果'},
                    'reputation_results': {'type': 'dict', 'required': False, 'description': '信誉评估结果'}
                }
            },
            {
                'name': 'scan_file',
                'description': '文件安全扫描',
                'parameters': {
                    'file_path': {'type': 'str', 'required': True, 'description': '文件路径'},
                    'scan_type': {'type': 'str', 'required': False, 'description': '扫描类型：code/dependency/config'}
                }
            }
        ]
    }
    
    # 危险代码模式
    DANGEROUS_PATTERNS = {
        'python': {
            'eval_exec': [
                (r'\beval\s*\(', 'HIGH', '使用 eval() 可能执行任意代码'),
                (r'\bexec\s*\(', 'HIGH', '使用 exec() 可能执行任意代码'),
                (r'\bcompile\s*\(', 'MEDIUM', '使用 compile() 可能编译恶意代码'),
            ],
            'sql_injection': [
                (r'execute\s*\(\s*["\'].*%.*["\']', 'HIGH', '可能存在 SQL 注入风险'),
                (r'cursor\.execute\s*\([^,]+%', 'HIGH', '字符串格式化 SQL 查询可能导致注入'),
            ],
            'file_operations': [
                (r'\bopen\s*\([^)]*["\'].*\+.*["\']', 'MEDIUM', '文件打开模式包含写入权限'),
                (r'\bos\.remove\s*\(', 'MEDIUM', '删除文件操作'),
                (r'\bshutil\.rmtree\s*\(', 'HIGH', '递归删除目录'),
            ],
            'network': [
                (r'\brequests\.(get|post|put|delete)\s*\([^)]*url\s*=', 'LOW', '网络请求操作'),
                (r'\bsocket\.', 'MEDIUM', '底层网络操作'),
                (r'\bsubprocess\.(call|run|Popen)\s*\(', 'HIGH', '执行系统命令'),
            ],
            'crypto': [
                (r'\bhashlib\.md5\s*\(', 'MEDIUM', '使用 MD5 哈希（不安全）'),
                (r'\bhashlib\.sha1\s*\(', 'MEDIUM', '使用 SHA1 哈希（不安全）'),
                (r'\brandom\.(random|randint|choice)\s*\(', 'LOW', '使用伪随机数生成器'),
            ],
            'deserialization': [
                (r'\bpickle\.load\s*\(', 'HIGH', '反序列化 pickle 数据可能执行恶意代码'),
                (r'\byaml\.load\s*\([^)]*\)', 'HIGH', 'yaml.load 可能执行任意代码（应使用 safe_load）'),
                (r'\bmarshal\.load\s*\(', 'HIGH', '反序列化 marshal 数据'),
            ],
        },
        'javascript': {
            'eval_exec': [
                (r'\beval\s*\(', 'HIGH', '使用 eval() 可能执行任意代码'),
                (r'\bFunction\s*\(', 'HIGH', '使用 Function 构造函数可能执行任意代码'),
                (r'\bsetTimeout\s*\(\s*["\']', 'MEDIUM', 'setTimeout 使用字符串参数'),
                (r'\bsetInterval\s*\(\s*["\']', 'MEDIUM', 'setInterval 使用字符串参数'),
            ],
            'dom_xss': [
                (r'\.innerHTML\s*=', 'MEDIUM', '直接设置 innerHTML 可能导致 XSS'),
                (r'\.outerHTML\s*=', 'MEDIUM', '直接设置 outerHTML 可能导致 XSS'),
                (r'document\.write\s*\(', 'HIGH', '使用 document.write'),
            ],
            'network': [
                (r'\bfetch\s*\([^)]*url', 'LOW', '网络请求操作'),
                (r'\bXMLHttpRequest\b', 'LOW', '使用 XMLHttpRequest'),
            ],
        },
        'general': {
            'secrets': [
                (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']+["\']', 'HIGH', '代码中包含硬编码密码'),
                (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][^"\']+["\']', 'HIGH', '代码中包含硬编码 API 密钥'),
                (r'(?i)(secret|token)\s*[=:]\s*["\'][^"\']+["\']', 'HIGH', '代码中包含硬编码密钥/令牌'),
                (r'(?i)private[_-]?key\s*[=:]', 'HIGH', '代码中包含私钥'),
            ],
            'hardcoded': [
                (r'(?i)(localhost|127\.0\.0\.1|0\.0\.0\.0)', 'LOW', '包含本地地址'),
                (r'(?i)(admin|root|administrator)', 'LOW', '包含管理员相关字符串'),
            ],
        }
    }
    
    # 权限风险等级
    PERMISSION_RISKS = {
        # 文件系统权限
        'read_file': {'risk': 'LOW', 'score': 10, 'description': '读取文件权限'},
        'write_file': {'risk': 'MEDIUM', 'score': 30, 'description': '写入文件权限'},
        'delete_file': {'risk': 'HIGH', 'score': 50, 'description': '删除文件权限'},
        'read_directory': {'risk': 'LOW', 'score': 10, 'description': '读取目录权限'},
        'write_directory': {'risk': 'MEDIUM', 'score': 30, 'description': '写入目录权限'},
        
        # 网络权限
        'network_access': {'risk': 'MEDIUM', 'score': 25, 'description': '网络访问权限'},
        'network_bind': {'risk': 'HIGH', 'score': 40, 'description': '网络监听权限'},
        'internet_access': {'risk': 'MEDIUM', 'score': 25, 'description': '互联网访问权限'},
        
        # 系统权限
        'execute_command': {'risk': 'HIGH', 'score': 60, 'description': '执行系统命令权限'},
        'read_environment': {'risk': 'MEDIUM', 'score': 20, 'description': '读取环境变量权限'},
        'write_environment': {'risk': 'HIGH', 'score': 50, 'description': '修改环境变量权限'},
        'access_registry': {'risk': 'HIGH', 'score': 50, 'description': '访问注册表权限'},
        
        # 设备权限
        'camera_access': {'risk': 'HIGH', 'score': 40, 'description': '摄像头访问权限'},
        'microphone_access': {'risk': 'HIGH', 'score': 40, 'description': '麦克风访问权限'},
        'location_access': {'risk': 'MEDIUM', 'score': 30, 'description': '位置信息访问权限'},
        'contacts_access': {'risk': 'HIGH', 'score': 50, 'description': '联系人访问权限'},
        
        # 数据权限
        'read_data': {'risk': 'LOW', 'score': 15, 'description': '读取数据权限'},
        'write_data': {'risk': 'MEDIUM', 'score': 30, 'description': '写入数据权限'},
        'delete_data': {'risk': 'HIGH', 'score': 50, 'description': '删除数据权限'},
    }
    
    # 来源信誉白名单
    TRUSTED_SOURCES = {
        'github': [
            'microsoft/', 'google/', 'facebook/', 'amazon/', 'apple/',
            'tensorflow/', 'pytorch/', 'mozilla/', 'nodejs/', 'python/',
        ],
        'pypi': [
            'requests', 'numpy', 'pandas', 'flask', 'django', 'pytest',
            'pip', 'setuptools', 'wheel', 'virtualenv',
        ],
        'npm': [
            'express', 'react', 'vue', 'angular', 'lodash', 'axios',
            'typescript', 'webpack', 'babel', 'eslint',
        ]
    }
    
    def __init__(self):
        """初始化安全扫描技能"""
        self.scan_history = []
        self.reputation_cache = {}
    
    def execute(self, operation: str, **kwargs) -> Dict:
        """
        执行安全扫描操作
        
        Args:
            operation: 操作类型
            **kwargs: 操作参数
            
        Returns:
            扫描结果
        """
        operations = {
            'scan_code': self._scan_code,
            'analyze_permissions': self._analyze_permissions,
            'evaluate_reputation': self._evaluate_reputation,
            'calculate_security_score': self._calculate_security_score,
            'scan_file': self._scan_file,
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
            
            # 记录扫描历史
            self.scan_history.append({
                'operation': operation,
                'timestamp': result['timestamp'],
                'success': result.get('success', True)
            })
            
            return result
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'operation': operation,
                'timestamp': datetime.now().isoformat()
            }
            
            self.scan_history.append({
                'operation': operation,
                'timestamp': error_result['timestamp'],
                'success': False,
                'error': str(e)
            })
            
            return error_result
    
    def _scan_code(self, code: str, language: str = 'python', scan_level: str = 'standard') -> Dict:
        """
        静态代码安全扫描
        
        Args:
            code: 待扫描的代码
            language: 编程语言
            scan_level: 扫描级别（basic/standard/deep）
            
        Returns:
            扫描结果
        """
        issues = []
        warnings = []
        info = []
        
        # 按语言扫描
        lang_lower = language.lower()
        if lang_lower in self.DANGEROUS_PATTERNS:
            patterns = self.DANGEROUS_PATTERNS[lang_lower]
            for category, pattern_list in patterns.items():
                for pattern, risk_level, description in pattern_list:
                    matches = re.finditer(pattern, code, re.MULTILINE)
                    for match in matches:
                        line_num = code[:match.start()].count('\n') + 1
                        issue = {
                            'type': category,
                            'risk_level': risk_level,
                            'description': description,
                            'line': line_num,
                            'pattern': pattern,
                            'matched_code': match.group(0)
                        }
                        
                        if risk_level == 'HIGH':
                            issues.append(issue)
                        elif risk_level == 'MEDIUM':
                            warnings.append(issue)
                        else:
                            info.append(issue)
        
        # 通用模式扫描（所有语言）
        for category, pattern_list in self.DANGEROUS_PATTERNS.get('general', {}).items():
            for pattern, risk_level, description in pattern_list:
                matches = re.finditer(pattern, code, re.MULTILINE)
                for match in matches:
                    line_num = code[:match.start()].count('\n') + 1
                    issue = {
                        'type': category,
                        'risk_level': risk_level,
                        'description': description,
                        'line': line_num,
                        'pattern': pattern,
                        'matched_code': match.group(0)
                    }
                    
                    if risk_level == 'HIGH':
                        issues.append(issue)
                    elif risk_level == 'MEDIUM':
                        warnings.append(issue)
                    else:
                        info.append(issue)
        
        # 计算代码安全评分
        total_lines = code.count('\n') + 1
        score = self._calculate_code_security_score(issues, warnings, info, total_lines)
        
        return {
            'scan_type': 'code_scan',
            'language': language,
            'scan_level': scan_level,
            'total_lines': total_lines,
            'issues_count': len(issues),
            'warnings_count': len(warnings),
            'info_count': len(info),
            'issues': issues,
            'warnings': warnings,
            'info': info,
            'security_score': score,
            'risk_level': self._get_risk_level(score)
        }
    
    def _analyze_permissions(self, permissions: List[str], context: str = '') -> Dict:
        """
        权限分析
        
        Args:
            permissions: 权限列表
            context: 使用场景
            
        Returns:
            分析结果
        """
        analyzed_permissions = []
        total_risk_score = 0
        risk_distribution = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0}
        
        for perm in permissions:
            perm_lower = perm.lower()
            
            # 查找匹配的权限定义
            perm_info = None
            for known_perm, info in self.PERMISSION_RISKS.items():
                if known_perm in perm_lower or perm_lower in known_perm:
                    perm_info = info
                    break
            
            if perm_info:
                analyzed_permissions.append({
                    'permission': perm,
                    'risk_level': perm_info['risk'],
                    'risk_score': perm_info['score'],
                    'description': perm_info['description']
                })
                total_risk_score += perm_info['score']
                risk_distribution[perm_info['risk']] += 1
            else:
                # 未知权限
                analyzed_permissions.append({
                    'permission': perm,
                    'risk_level': 'UNKNOWN',
                    'risk_score': 15,
                    'description': '未识别的权限'
                })
                total_risk_score += 15
                risk_distribution['MEDIUM'] += 1
        
        # 计算整体风险
        max_possible_score = len(permissions) * 60  # 假设所有权限都是最高风险
        normalized_score = (total_risk_score / max_possible_score) * 100 if max_possible_score > 0 else 0
        security_score = max(0, 100 - normalized_score)
        
        return {
            'scan_type': 'permission_analysis',
            'context': context,
            'total_permissions': len(permissions),
            'analyzed_permissions': analyzed_permissions,
            'risk_distribution': risk_distribution,
            'total_risk_score': total_risk_score,
            'security_score': round(security_score, 2),
            'risk_level': self._get_risk_level(security_score),
            'recommendations': self._generate_permission_recommendations(analyzed_permissions, context)
        }
    
    def _evaluate_reputation(self, source: str, source_type: str = 'github') -> Dict:
        """
        来源信誉评估
        
        Args:
            source: 来源标识
            source_type: 来源类型
            
        Returns:
            评估结果
        """
        source_lower = source.lower()
        
        # 检查缓存
        cache_key = f"{source_type}:{source_lower}"
        if cache_key in self.reputation_cache:
            return self.reputation_cache[cache_key]
        
        # 基础评分
        base_score = 50  # 默认中等评分
        factors = []
        
        # 检查是否在白名单中
        is_trusted = False
        if source_type.lower() in self.TRUSTED_SOURCES:
            for trusted in self.TRUSTED_SOURCES[source_type.lower()]:
                if trusted.lower() in source_lower:
                    is_trusted = True
                    base_score += 30
                    factors.append({
                        'factor': 'trusted_source',
                        'impact': '+30',
                        'description': f'来源在{source_type}白名单中'
                    })
                    break
        
        # 来源类型评分
        type_scores = {
            'github': 10,
            'pypi': 5,
            'npm': 5,
            'official': 20,
            'verified': 15,
        }
        
        if source_type.lower() in type_scores:
            base_score += type_scores[source_type.lower()]
            factors.append({
                'factor': 'source_type',
                'impact': f'+{type_scores[source_type.lower()]}',
                'description': f'来源类型：{source_type}'
            })
        
        # URL 来源检查
        if source_type.lower() == 'url':
            if 'https://' in source_lower:
                base_score += 5
                factors.append({
                    'factor': 'https',
                    'impact': '+5',
                    'description': '使用 HTTPS 协议'
                })
            
            suspicious_tlds = ['.ru', '.cn', '.tk', '.ml', '.ga', '.cf']
            for tld in suspicious_tlds:
                if tld in source_lower:
                    base_score -= 10
                    factors.append({
                        'factor': 'suspicious_tld',
                        'impact': '-10',
                        'description': f'包含可疑域名后缀：{tld}'
                    })
                    break
        
        # 限制分数范围
        final_score = max(0, min(100, base_score))
        
        result = {
            'scan_type': 'reputation_evaluation',
            'source': source,
            'source_type': source_type,
            'is_trusted': is_trusted,
            'reputation_score': round(final_score, 2),
            'risk_level': self._get_risk_level(final_score),
            'factors': factors,
            'recommendations': self._generate_reputation_recommendations(source, source_type, final_score)
        }
        
        # 缓存结果
        self.reputation_cache[cache_key] = result
        
        return result
    
    def _calculate_security_score(self, scan_results: Dict, 
                                  permission_results: Optional[Dict] = None,
                                  reputation_results: Optional[Dict] = None) -> Dict:
        """
        计算综合安全评分
        
        Args:
            scan_results: 扫描结果
            permission_results: 权限分析结果
            reputation_results: 信誉评估结果
            
        Returns:
            综合评分结果
        """
        scores = {}
        weights = {}
        
        # 代码安全评分
        if 'security_score' in scan_results:
            scores['code_security'] = scan_results['security_score']
            weights['code_security'] = 0.5  # 50% 权重
        
        # 权限安全评分
        if permission_results and 'security_score' in permission_results:
            scores['permission_security'] = permission_results['security_score']
            weights['permission_security'] = 0.3  # 30% 权重
        
        # 信誉评分
        if reputation_results and 'reputation_score' in reputation_results:
            scores['reputation'] = reputation_results['reputation_score']
            weights['reputation'] = 0.2  # 20% 权重
        
        # 计算加权平均
        if not scores:
            return {
                'success': False,
                'error': '没有可用的评分数据'
            }
        
        total_weight = sum(weights.values())
        weighted_score = sum(scores[key] * weights[key] for key in scores)
        final_score = weighted_score / total_weight if total_weight > 0 else 0
        
        # 确定风险等级
        risk_level = self._get_risk_level(final_score)
        
        return {
            'scan_type': 'comprehensive_security_score',
            'individual_scores': scores,
            'weights': weights,
            'final_score': round(final_score, 2),
            'risk_level': risk_level,
            'risk_level_description': self._get_risk_level_description(risk_level),
            'recommendations': self._generate_comprehensive_recommendations(scores, risk_level)
        }
    
    def _scan_file(self, file_path: str, scan_type: str = 'code') -> Dict:
        """
        文件安全扫描
        
        Args:
            file_path: 文件路径
            scan_type: 扫描类型
            
        Returns:
            扫描结果
        """
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f'文件不存在：{file_path}'
            }
        
        try:
            if scan_type == 'code':
                # 代码文件扫描
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检测语言
                language = self._detect_language(file_path)
                
                return self._scan_code(content, language)
            
            elif scan_type == 'dependency':
                # 依赖文件扫描
                return self._scan_dependency_file(file_path)
            
            elif scan_type == 'config':
                # 配置文件扫描
                return self._scan_config_file(file_path)
            
            else:
                return {
                    'success': False,
                    'error': f'不支持的扫描类型：{scan_type}'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'扫描失败：{str(e)}'
            }
    
    def _detect_language(self, file_path: str) -> str:
        """检测文件编程语言"""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.jsx': 'javascript',
            '.tsx': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'cpp',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
        }
        
        ext = os.path.splitext(file_path)[1].lower()
        return ext_map.get(ext, 'python')  # 默认 Python
    
    def _scan_dependency_file(self, file_path: str) -> Dict:
        """扫描依赖文件"""
        filename = os.path.basename(file_path)
        dependencies = []
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # requirements.txt
            if filename == 'requirements.txt':
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # 解析包名
                        match = re.match(r'^([a-zA-Z0-9_-]+)', line)
                        if match:
                            package = match.group(1)
                            dependencies.append({
                                'name': package,
                                'version': 'unspecified',
                                'source': 'pypi'
                            })
                            
                            # 检查是否有固定版本
                            if '==' not in line and '>=' not in line:
                                issues.append({
                                    'type': 'version_not_pinned',
                                    'package': package,
                                    'risk_level': 'MEDIUM',
                                    'description': '依赖版本未固定'
                                })
            
            # package.json
            elif filename == 'package.json':
                data = json.loads(content)
                deps = data.get('dependencies', {})
                dev_deps = data.get('devDependencies', {})
                
                for dep, version in deps.items():
                    dependencies.append({
                        'name': dep,
                        'version': version,
                        'source': 'npm',
                        'type': 'production'
                    })
                
                for dep, version in dev_deps.items():
                    dependencies.append({
                        'name': dep,
                        'version': version,
                        'source': 'npm',
                        'type': 'development'
                    })
            
            return {
                'scan_type': 'dependency_scan',
                'file': filename,
                'total_dependencies': len(dependencies),
                'dependencies': dependencies,
                'issues': issues,
                'issues_count': len(issues)
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'解析依赖文件失败：{str(e)}'
            }
    
    def _scan_config_file(self, file_path: str) -> Dict:
        """扫描配置文件"""
        filename = os.path.basename(file_path)
        issues = []
        info = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 检查敏感信息
            sensitive_patterns = [
                (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']+["\']', 'HIGH', '包含密码'),
                (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][^"\']+["\']', 'HIGH', '包含 API 密钥'),
                (r'(?i)(secret|token)\s*[=:]\s*["\'][^"\']+["\']', 'HIGH', '包含密钥/令牌'),
                (r'(?i)(private[_-]?key)\s*[=:]', 'HIGH', '包含私钥'),
                (r'(?i)(aws[_-]?access|aws[_-]?secret)', 'HIGH', '包含 AWS 凭证'),
            ]
            
            for pattern, risk_level, description in sensitive_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    issues.append({
                        'type': 'sensitive_info',
                        'risk_level': risk_level,
                        'description': f'配置文件{description}',
                        'count': len(matches)
                    })
            
            return {
                'scan_type': 'config_scan',
                'file': filename,
                'issues_count': len(issues),
                'issues': issues,
                'info_count': len(info),
                'info': info
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'扫描配置文件失败：{str(e)}'
            }
    
    def _calculate_code_security_score(self, issues: List, warnings: List, 
                                       info: List, total_lines: int) -> float:
        """计算代码安全评分"""
        if total_lines == 0:
            return 100.0
        
        # 问题权重
        issue_weights = {
            'HIGH': 10,
            'MEDIUM': 5,
            'LOW': 2
        }
        
        # 计算总扣分
        total_deduction = 0
        for issue in issues:
            total_deduction += issue_weights.get(issue['risk_level'], 5)
        
        for warning in warnings:
            total_deduction += issue_weights.get(warning['risk_level'], 3)
        
        for info_item in info:
            total_deduction += issue_weights.get(info_item['risk_level'], 1)
        
        # 计算密度（每千行问题数）
        density = (len(issues) + len(warnings) * 0.5 + len(info) * 0.2) / (total_lines / 1000)
        
        # 基础分 100，根据问题和密度扣分
        score = 100 - total_deduction - (density * 0.1)
        
        return max(0, min(100, round(score, 2)))
    
    def _get_risk_level(self, score: float) -> str:
        """根据评分获取风险等级"""
        if score >= 90:
            return 'LOW'
        elif score >= 70:
            return 'MEDIUM'
        elif score >= 50:
            return 'HIGH'
        else:
            return 'CRITICAL'
    
    def _get_risk_level_description(self, risk_level: str) -> str:
        """获取风险等级描述"""
        descriptions = {
            'LOW': '风险较低，可以安全使用',
            'MEDIUM': '存在中等风险，建议审查后使用',
            'HIGH': '存在较高风险，需要仔细审查',
            'CRITICAL': '风险极高，不建议使用'
        }
        return descriptions.get(risk_level, '未知风险等级')
    
    def _generate_permission_recommendations(self, permissions: List[Dict], context: str) -> List[str]:
        """生成权限建议"""
        recommendations = []
        
        high_risk_perms = [p for p in permissions if p.get('risk_level') == 'HIGH']
        
        if high_risk_perms:
            recommendations.append(f'发现 {len(high_risk_perms)} 个高风险权限，请确认是否必要')
            recommendations.append('建议遵循最小权限原则，仅申请必需的权限')
        
        unknown_perms = [p for p in permissions if p.get('risk_level') == 'UNKNOWN']
        if unknown_perms:
            recommendations.append(f'发现 {len(unknown_perms)} 个未识别的权限，建议详细了解其用途')
        
        if context:
            recommendations.append(f'请根据使用场景 "{context}" 评估权限的合理性')
        
        if not recommendations:
            recommendations.append('权限配置相对合理')
        
        return recommendations
    
    def _generate_reputation_recommendations(self, source: str, source_type: str, 
                                            score: float) -> List[str]:
        """生成信誉建议"""
        recommendations = []
        
        if score < 50:
            recommendations.append('来源信誉较低，建议谨慎使用')
            recommendations.append('建议查找更可信的替代来源')
        elif score < 70:
            recommendations.append('来源信誉中等，建议进一步验证')
            recommendations.append('可以查看其他用户的评价和使用情况')
        else:
            recommendations.append('来源信誉良好')
        
        if source_type == 'github':
            recommendations.append('建议查看仓库的 star 数、贡献者、最近更新时间等指标')
        elif source_type == 'pypi' or source_type == 'npm':
            recommendations.append('建议查看包的下载量、维护频率、issue 响应情况')
        
        return recommendations
    
    def _generate_comprehensive_recommendations(self, scores: Dict, 
                                                risk_level: str) -> List[str]:
        """生成综合建议"""
        recommendations = []
        
        if risk_level == 'CRITICAL':
            recommendations.append('⚠️ 综合风险极高，强烈建议不要使用')
            recommendations.append('请全面审查代码、权限和来源')
        elif risk_level == 'HIGH':
            recommendations.append('⚠️ 存在较高风险，需要仔细审查')
            recommendations.append('建议逐一检查发现的问题')
        elif risk_level == 'MEDIUM':
            recommendations.append('⚠️ 存在中等风险，建议审查后使用')
            recommendations.append('可以优先处理高风险问题')
        else:
            recommendations.append('✅ 整体风险可控')
        
        # 针对各维度的建议
        if 'code_security' in scores and scores['code_security'] < 70:
            recommendations.append('代码安全评分较低，建议修复发现的安全问题')
        
        if 'permission_security' in scores and scores['permission_security'] < 70:
            recommendations.append('权限风险较高，建议重新评估权限需求')
        
        if 'reputation' in scores and scores['reputation'] < 70:
            recommendations.append('来源信誉较低，建议寻找更可信的替代方案')
        
        return recommendations


# 测试代码
if __name__ == '__main__':
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    scanner = SecurityScannerSkill()
    
    print("=" * 60)
    print("安全扫描技能测试")
    print("=" * 60)
    
    # 测试 1: 代码扫描
    print("\n[测试 1] 代码安全扫描")
    test_code = """
import os
import pickle
import subprocess

password = "secret123"
api_key = "sk-1234567890"

def dangerous_func(user_input):
    eval(user_input)
    exec("print('hello')")
    pickle.load(open('data.pkl', 'rb'))
    subprocess.call(f'echo {user_input}', shell=True)
    os.remove('/important/file.txt')
"""
    
    result = scanner.execute('scan_code', code=test_code, language='python')
    print(f"安全评分：{result.get('security_score', 'N/A')}")
    print(f"风险等级：{result.get('risk_level', 'N/A')}")
    print(f"发现问题数：{result.get('issues_count', 0)}")
    print(f"警告数：{result.get('warnings_count', 0)}")
    
    if result.get('issues'):
        print("\n主要问题:")
        for issue in result['issues'][:3]:
            print(f"  - 第{issue['line']}行：{issue['description']} [{issue['risk_level']}]")
    
    # 测试 2: 权限分析
    print("\n[测试 2] 权限分析")
    permissions = [
        'read_file',
        'write_file',
        'network_access',
        'execute_command',
        'camera_access',
        'contacts_access'
    ]
    
    result = scanner.execute('analyze_permissions', permissions=permissions, 
                            context='文档处理工具')
    print(f"安全评分：{result.get('security_score', 'N/A')}")
    print(f"风险等级：{result.get('risk_level', 'N/A')}")
    print(f"总权限数：{result.get('total_permissions', 0)}")
    print(f"风险分布：{result.get('risk_distribution', {})}")
    
    if result.get('recommendations'):
        print("\n建议:")
        for rec in result['recommendations'][:3]:
            print(f"  - {rec}")
    
    # 测试 3: 信誉评估
    print("\n[测试 3] 来源信誉评估")
    sources = [
        ('microsoft/transformers', 'github'),
        ('unknown-user/suspicious-package', 'github'),
        ('requests', 'pypi'),
        ('https://example.com/package.zip', 'url')
    ]
    
    for source, source_type in sources:
        result = scanner.execute('evaluate_reputation', source=source, 
                                source_type=source_type)
        print(f"\n来源：{source}")
        print(f"  信誉评分：{result.get('reputation_score', 'N/A')}")
        print(f"  风险等级：{result.get('risk_level', 'N/A')}")
        print(f"  是否可信：{result.get('is_trusted', False)}")
    
    # 测试 4: 综合评分
    print("\n[测试 4] 综合安全评分")
    code_result = scanner.execute('scan_code', code=test_code, language='python')
    perm_result = scanner.execute('analyze_permissions', permissions=permissions)
    rep_result = scanner.execute('evaluate_reputation', 
                                source='microsoft/transformers', 
                                source_type='github')
    
    comprehensive = scanner.execute('calculate_security_score',
                                   scan_results=code_result,
                                   permission_results=perm_result,
                                   reputation_results=rep_result)
    
    print(f"综合评分：{comprehensive.get('final_score', 'N/A')}")
    print(f"综合风险等级：{comprehensive.get('risk_level', 'N/A')}")
    print(f"风险描述：{comprehensive.get('risk_level_description', '')}")
    
    if comprehensive.get('recommendations'):
        print("\n综合建议:")
        for rec in comprehensive['recommendations']:
            print(f"  - {rec}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
