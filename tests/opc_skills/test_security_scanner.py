"""
安全扫描技能单元测试
"""

import pytest
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_skills.security_scanner import SecurityScannerSkill


class TestSecurityScannerSkill:
    """安全扫描技能测试类"""
    
    @pytest.fixture
    def scanner(self):
        """创建扫描器实例"""
        return SecurityScannerSkill()
    
    def test_metadata(self, scanner):
        """测试技能元数据"""
        assert scanner.METADATA['name'] == 'security_scanner'
        assert scanner.METADATA['version'] == '1.0.0'
        assert 'security' in scanner.METADATA['category']
        assert len(scanner.METADATA['operations']) >= 5
    
    def test_scan_code_basic(self, scanner):
        """测试基础代码扫描"""
        safe_code = """
def add(a, b):
    return a + b

def greet(name):
    print(f"Hello, {name}!")
"""
        result = scanner.execute('scan_code', code=safe_code, language='python')
        
        assert result['success'] is True
        assert result['scan_type'] == 'code_scan'
        assert result['language'] == 'python'
        assert 'security_score' in result
        assert result['security_score'] >= 80  # 安全代码应该高分
    
    def test_scan_code_dangerous_patterns(self, scanner):
        """测试危险代码模式检测"""
        dangerous_code = """
import pickle
import subprocess

password = "secret123"

def risky_func(user_input):
    eval(user_input)
    pickle.load(open('data.pkl', 'rb'))
    subprocess.call(user_input, shell=True)
"""
        result = scanner.execute('scan_code', code=dangerous_code, language='python')
        
        assert result['success'] is True
        assert result['issues_count'] > 0  # 应该检测到问题
        assert result['security_score'] < 70  # 危险代码应该低分
        
        # 检查是否检测到特定问题
        issue_types = [issue['type'] for issue in result['issues']]
        assert any('eval_exec' in t for t in issue_types) or \
               any('deserialization' in t for t in issue_types)
    
    def test_scan_code_secrets_detection(self, scanner):
        """测试敏感信息检测"""
        code_with_secrets = """
API_KEY = "sk-1234567890abcdef"
password = "admin123"
secret_token = "ghp_xxxxxxxxxxxx"
"""
        result = scanner.execute('scan_code', code=code_with_secrets, language='python')
        
        assert result['success'] is True
        # 应该检测到硬编码的敏感信息
        assert result['issues_count'] > 0 or result['warnings_count'] > 0
    
    def test_analyze_permissions_basic(self, scanner):
        """测试基础权限分析"""
        permissions = ['read_file', 'write_file', 'network_access']
        
        result = scanner.execute('analyze_permissions', permissions=permissions)
        
        assert result['success'] is True
        assert result['scan_type'] == 'permission_analysis'
        assert result['total_permissions'] == 3
        assert 'security_score' in result
        assert 'risk_distribution' in result
    
    def test_analyze_permissions_high_risk(self, scanner):
        """测试高风险权限分析"""
        high_risk_permissions = [
            'execute_command',
            'delete_file',
            'camera_access',
            'contacts_access',
            'write_environment'
        ]
        
        result = scanner.execute('analyze_permissions', 
                                permissions=high_risk_permissions,
                                context='测试工具')
        
        assert result['success'] is True
        assert result['total_permissions'] == 5
        # 高风险权限应该导致较低的评分
        assert result['security_score'] < 60
        assert result['risk_distribution']['HIGH'] > 0
    
    def test_analyze_permissions_unknown(self, scanner):
        """测试未知权限处理"""
        unknown_permissions = [
            'custom_permission_1',
            'unknown_permission_2'
        ]
        
        result = scanner.execute('analyze_permissions', permissions=unknown_permissions)
        
        assert result['success'] is True
        # 未知权限应该有默认处理
        assert result['total_permissions'] == 2
    
    def test_evaluate_reputation_trusted_source(self, scanner):
        """测试可信来源评估"""
        result = scanner.execute('evaluate_reputation', 
                                source='microsoft/transformers',
                                source_type='github')
        
        assert result['success'] is True
        assert result['scan_type'] == 'reputation_evaluation'
        # 微软的仓库应该有较高评分
        assert result['reputation_score'] >= 70
        assert result['is_trusted'] is True
    
    def test_evaluate_reputation_unknown_source(self, scanner):
        """测试未知来源评估"""
        result = scanner.execute('evaluate_reputation',
                                source='unknown-user/suspicious-package',
                                source_type='github')
        
        assert result['success'] is True
        # 未知来源应该有中等或较低评分
        assert result['reputation_score'] < 80
    
    def test_evaluate_reputation_pypi_package(self, scanner):
        """测试 PyPI 包评估"""
        result = scanner.execute('evaluate_reputation',
                                source='requests',
                                source_type='pypi')
        
        assert result['success'] is True
        # requests 是知名包，应该有较高评分
        assert result['reputation_score'] >= 60
    
    def test_calculate_security_score_comprehensive(self, scanner):
        """测试综合安全评分计算"""
        # 准备各项扫描结果
        code_result = scanner.execute('scan_code', 
                                     code='def safe(): return 1',
                                     language='python')
        perm_result = scanner.execute('analyze_permissions',
                                     permissions=['read_file'])
        rep_result = scanner.execute('evaluate_reputation',
                                    source='microsoft/test',
                                    source_type='github')
        
        # 计算综合评分
        comprehensive = scanner.execute('calculate_security_score',
                                       scan_results=code_result,
                                       permission_results=perm_result,
                                       reputation_results=rep_result)
        
        assert comprehensive['success'] is True
        assert 'final_score' in comprehensive
        assert 'risk_level' in comprehensive
        assert 'recommendations' in comprehensive
        assert 0 <= comprehensive['final_score'] <= 100
    
    def test_calculate_security_score_partial(self, scanner):
        """测试部分评分（缺少某些维度）"""
        code_result = scanner.execute('scan_code',
                                     code='x = 1',
                                     language='python')
        
        # 只有代码扫描结果
        result = scanner.execute('calculate_security_score',
                               scan_results=code_result)
        
        assert result['success'] is True
        assert 'final_score' in result
        # 应该只有代码安全权重
        assert 'code_security' in result.get('individual_scores', {})
    
    def test_scan_file_code(self, scanner, tmp_path):
        """测试文件扫描（代码文件）"""
        # 创建临时 Python 文件
        test_file = tmp_path / "test_code.py"
        test_file.write_text("""
def hello():
    print("Hello, World!")
""")
        
        result = scanner.execute('scan_file', 
                                file_path=str(test_file),
                                scan_type='code')
        
        assert result['success'] is True
        assert result['scan_type'] == 'code_scan'
        assert 'security_score' in result
    
    def test_scan_file_not_found(self, scanner):
        """测试文件不存在的情况"""
        result = scanner.execute('scan_file',
                                file_path='/nonexistent/file.py',
                                scan_type='code')
        
        assert result['success'] is False
        assert 'error' in result
        assert '不存在' in result['error']
    
    def test_scan_dependency_file(self, scanner, tmp_path):
        """测试依赖文件扫描"""
        # 创建临时 requirements.txt
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("""
requests==2.28.0
numpy>=1.20.0
pandas
# comment
flask
""")
        
        result = scanner.execute('scan_file',
                                file_path=str(req_file),
                                scan_type='dependency')
        
        assert result['success'] is True
        assert result['scan_type'] == 'dependency_scan'
        assert result['total_dependencies'] >= 3
        # 应该检测到未固定版本的依赖
        assert result['issues_count'] > 0
    
    def test_scan_config_file(self, scanner, tmp_path):
        """测试配置文件扫描"""
        # 创建包含敏感信息的配置文件
        config_file = tmp_path / "config.ini"
        config_file.write_text("""
[database]
host = localhost
port = 5432
password = "super_secret_123"

[api]
api_key = "sk-xxxxxxxxx"
""")
        
        result = scanner.execute('scan_file',
                                file_path=str(config_file),
                                scan_type='config')
        
        assert result['success'] is True
        assert result['scan_type'] == 'config_scan'
        # 应该检测到敏感信息
        assert result['issues_count'] > 0
    
    def test_execute_invalid_operation(self, scanner):
        """测试无效操作"""
        result = scanner.execute('invalid_operation')
        
        assert result['success'] is False
        assert 'error' in result
        assert 'available_operations' in result
    
    def test_scan_code_different_languages(self, scanner):
        """测试不同编程语言的代码扫描"""
        # JavaScript 代码
        js_code = """
function test() {
    eval("console.log('test')");
    document.getElementById('app').innerHTML = userInput;
}
"""
        result = scanner.execute('scan_code', code=js_code, language='javascript')
        
        assert result['success'] is True
        assert result['language'] == 'javascript'
        # 应该检测到 eval 和 innerHTML 风险
        assert result['issues_count'] > 0 or result['warnings_count'] > 0
    
    def test_get_risk_level(self, scanner):
        """测试风险等级判断"""
        assert scanner._get_risk_level(95) == 'LOW'
        assert scanner._get_risk_level(80) == 'MEDIUM'
        assert scanner._get_risk_level(60) == 'HIGH'
        assert scanner._get_risk_level(40) == 'CRITICAL'
    
    def test_scan_history_tracking(self, scanner):
        """测试扫描历史追踪"""
        initial_count = len(scanner.scan_history)
        
        # 执行几次扫描
        scanner.execute('scan_code', code='x = 1', language='python')
        scanner.execute('analyze_permissions', permissions=['read_file'])
        
        new_count = len(scanner.scan_history)
        assert new_count == initial_count + 2
        
        # 检查历史记录格式
        last_scan = scanner.scan_history[-1]
        assert 'operation' in last_scan
        assert 'timestamp' in last_scan
        assert 'success' in last_scan


class TestSecurityScannerIntegration:
    """安全扫描技能集成测试"""
    
    @pytest.fixture
    def scanner(self):
        """创建扫描器实例"""
        return SecurityScannerSkill()
    
    def test_full_security_assessment(self, scanner):
        """测试完整安全评估流程"""
        # 模拟一个第三方库的评估
        code = """
import requests
import json

def fetch_data(url):
    response = requests.get(url)
    return response.json()
"""
        permissions = ['network_access', 'read_file']
        source = 'requests'
        source_type = 'pypi'
        
        # 1. 代码扫描
        code_result = scanner.execute('scan_code', code=code, language='python')
        
        # 2. 权限分析
        perm_result = scanner.execute('analyze_permissions', 
                                     permissions=permissions,
                                     context='网络请求工具')
        
        # 3. 信誉评估
        rep_result = scanner.execute('evaluate_reputation',
                                    source=source,
                                    source_type=source_type)
        
        # 4. 综合评分
        comprehensive = scanner.execute('calculate_security_score',
                                       scan_results=code_result,
                                       permission_results=perm_result,
                                       reputation_results=rep_result)
        
        # 验证结果
        assert code_result['success'] is True
        assert perm_result['success'] is True
        assert rep_result['success'] is True
        assert comprehensive['success'] is True
        
        # 综合评分应该在合理范围内
        assert 0 <= comprehensive['final_score'] <= 100
        
        # 应该有建议
        assert len(comprehensive.get('recommendations', [])) > 0
    
    def test_dangerous_code_assessment(self, scanner):
        """测试危险代码的完整评估"""
        dangerous_code = """
import pickle
import subprocess
import os

api_key = "sk-secret-key-123"

def process_user_input(user_input):
    eval(user_input)
    exec(f"print({user_input})")
    pickle.loads(user_input.encode())
    subprocess.call(user_input, shell=True)
    os.system(f"echo {user_input}")
"""
        
        permissions = [
            'execute_command',
            'read_file',
            'write_file',
            'delete_file',
            'network_access'
        ]
        
        # 代码扫描
        code_result = scanner.execute('scan_code', 
                                     code=dangerous_code,
                                     language='python')
        
        # 权限分析
        perm_result = scanner.execute('analyze_permissions',
                                     permissions=permissions)
        
        # 综合评分
        comprehensive = scanner.execute('calculate_security_score',
                                       scan_results=code_result,
                                       permission_results=perm_result)
        
        # 危险代码应该有低分和高风险评级
        assert code_result['issues_count'] > 3
        assert code_result['security_score'] < 50
        assert comprehensive['final_score'] < 50
        assert comprehensive['risk_level'] in ['HIGH', 'CRITICAL']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
