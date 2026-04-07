"""
微信配对功能单元测试

测试配对管理器、二维码生成器等功能
"""

import pytest
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from opc_manager.openclaw_protocol.pairing_manager import PairingManager
from opc_manager.openclaw_protocol.qr_generator import QRCodeGenerator


class TestPairingManager:
    """测试配对管理器"""
    
    @pytest.fixture
    def manager(self):
        """创建测试用的配对管理器"""
        # 使用临时目录
        import tempfile
        temp_dir = tempfile.mkdtemp()
        return PairingManager(data_dir=temp_dir)
    
    def test_generate_pairing_code(self, manager):
        """测试配对码生成"""
        code = manager.generate_pairing_code()
        
        # 长度应为 8
        assert len(code) == 8
        
        # 应全为大写
        assert code == code.upper()
        
        # 不应包含歧义字符（0O1I）
        assert '0' not in code
        assert 'O' not in code
        assert '1' not in code
        assert 'I' not in code
        
        # 所有字符应在可用字符集中
        for char in code:
            assert char in manager.AVAILABLE_CHARS
    
    def test_create_pairing_request(self, manager):
        """测试创建配对请求"""
        device_id = 'test_device_001'
        device_info = {'type': 'test'}
        
        code = manager.create_pairing_request(
            channel='wechat',
            device_id=device_id,
            device_info=device_info
        )
        
        # 应返回 8 位配对码
        assert len(code) == 8
        
        # 应在待处理列表中
        pending = manager.list_pending('wechat')
        assert len(pending) == 1
        assert pending[0]['code'] == code
        assert pending[0]['device_id'] == device_id
        assert pending[0]['channel'] == 'wechat'
    
    def test_create_pairing_request_limit(self, manager):
        """测试待处理请求上限"""
        # 创建 3 个请求（达到上限）
        for i in range(3):
            manager.create_pairing_request(
                channel='wechat',
                device_id=f'device_{i}',
                device_info={}
            )
        
        # 第 4 个应失败
        with pytest.raises(Exception) as exc_info:
            manager.create_pairing_request(
                channel='wechat',
                device_id='device_3',
                device_info={}
            )
        
        assert 'Too many pending pairing requests' in str(exc_info.value)
    
    def test_approve_pairing(self, manager):
        """测试批准配对"""
        # 创建配对请求
        code = manager.create_pairing_request(
            channel='wechat',
            device_id='test_device',
            device_info={'type': 'test'}
        )
        
        # 批准配对
        device_info = manager.approve_pairing(code)
        
        # 应返回设备信息
        assert device_info is not None
        # device_id 在 approved_devices 的 key 中
        assert 'test_device' in manager.approved_devices
        
        # 设备应在已批准列表中
        assert manager.is_device_approved('test_device')
        
        # 待处理列表应为空
        pending = manager.list_pending('wechat')
        assert len(pending) == 0
    
    def test_approve_invalid_code(self, manager):
        """测试批准无效配对码"""
        result = manager.approve_pairing('INVALID9')
        assert result is None
    
    def test_reject_pairing(self, manager):
        """测试拒绝配对"""
        # 创建配对请求
        code = manager.create_pairing_request(
            channel='wechat',
            device_id='test_device',
            device_info={}
        )
        
        # 拒绝配对
        success = manager.reject_pairing(code)
        assert success is True
        
        # 待处理列表应为空
        pending = manager.list_pending('wechat')
        assert len(pending) == 0
        
        # 再次拒绝应返回 False
        success = manager.reject_pairing(code)
        assert success is False
    
    def test_revoke_device(self, manager):
        """测试撤销设备"""
        # 创建并批准配对
        code = manager.create_pairing_request(
            channel='wechat',
            device_id='test_device',
            device_info={}
        )
        manager.approve_pairing(code)
        
        # 撤销设备
        success = manager.revoke_device('test_device')
        assert success is True
        
        # 设备应不再已批准
        assert not manager.is_device_approved('test_device')
    
    def test_cleanup_expired(self, manager):
        """测试清理过期请求"""
        # 创建配对请求
        code = manager.create_pairing_request(
            channel='wechat',
            device_id='test_device',
            device_info={}
        )
        
        # 手动设置过期时间（过期）
        manager.pending_pairings[code]['expires_at'] = datetime.now() - timedelta(hours=1)
        
        # 清理过期请求
        cleaned = manager.cleanup_expired()
        assert cleaned == 1
        
        # 待处理列表应为空
        pending = manager.list_pending('wechat')
        assert len(pending) == 0
    
    def test_list_pending(self, manager):
        """测试列出待处理请求"""
        # 创建多个请求
        codes = []
        for i in range(3):
            code = manager.create_pairing_request(
                channel='wechat',
                device_id=f'device_{i}',
                device_info={}
            )
            codes.append(code)
        
        # 列出所有
        pending = manager.list_pending()
        assert len(pending) == 3
        
        # 按频道过滤
        pending_wechat = manager.list_pending(channel='wechat')
        assert len(pending_wechat) == 3
        
        pending_other = manager.list_pending(channel='other')
        assert len(pending_other) == 0
    
    def test_list_approved(self, manager):
        """测试列出已批准设备"""
        # 创建并批准多个设备
        for i in range(3):
            code = manager.create_pairing_request(
                channel='wechat',
                device_id=f'device_{i}',
                device_info={'index': i}
            )
            manager.approve_pairing(code)
        
        # 列出所有
        approved = manager.list_approved()
        assert len(approved) == 3
        
        # 按频道过滤
        approved_wechat = manager.list_approved(channel='wechat')
        assert len(approved_wechat) == 3
    
    def test_get_stats(self, manager):
        """测试获取统计信息"""
        # 创建一些数据
        for i in range(2):
            code = manager.create_pairing_request(
                channel='wechat',
                device_id=f'device_{i}',
                device_info={}
            )
            manager.approve_pairing(code)
        
        # 创建 1 个待处理
        manager.create_pairing_request(
            channel='wechat',
            device_id='pending_device',
            device_info={}
        )
        
        # 获取统计
        stats = manager.get_stats()
        
        assert stats['pending_count'] == 1
        assert stats['approved_count'] == 2


class TestQRCodeGenerator:
    """测试二维码生成器"""
    
    @pytest.fixture
    def generator(self):
        """创建测试用的二维码生成器"""
        return QRCodeGenerator()
    
    def test_generate_pairing_qr(self, generator):
        """测试生成配对二维码"""
        try:
            qr_base64 = generator.generate_pairing_qr(
                pairing_code='ABCD1234',
                websocket_url='ws://localhost:18789/ws/openclaw',
                device_id='test_device'
            )
            
            # 应返回 Base64 字符串
            assert isinstance(qr_base64, str)
            assert qr_base64.startswith('data:image/png;base64,')
            
            # Base64 部分应非空
            base64_part = qr_base64.split(',')[1]
            assert len(base64_part) > 0
            
        except ImportError:
            # qrcode 库未安装
            pytest.skip("qrcode library not available")
    
    def test_generate_simple_qr(self, generator):
        """测试生成简单二维码"""
        try:
            qr_base64 = generator.generate_simple_qr('test data')
            
            assert isinstance(qr_base64, str)
            assert qr_base64.startswith('data:image/png;base64,')
            
        except ImportError:
            pytest.skip("qrcode library not available")
    
    def test_generate_ascii_qr(self, generator):
        """测试生成 ASCII 二维码"""
        try:
            ascii_qr = generator.generate_ascii_qr('ABCD1234')
            
            assert isinstance(ascii_qr, str)
            assert len(ascii_qr) > 0
            # ASCII 二维码应包含 Unicode 块字符或空格
            assert len(ascii_qr.strip()) > 0
            
        except ImportError:
            pytest.skip("qrcode library not available")
    
    def test_generate_pairing_code_display(self, generator):
        """测试生成配对码展示"""
        try:
            display = generator.generate_pairing_code_display('ABCD1234')
            
            assert isinstance(display, str)
            assert 'ABCD1234' in display
            assert '配对码' in display
            
        except ImportError:
            pytest.skip("qrcode library not available")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
