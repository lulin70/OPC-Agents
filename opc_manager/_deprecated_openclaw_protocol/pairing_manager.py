"""
配对管理器 - 微信集成配对功能

实现 OpenClaw 兼容的配对码生成、管理和设备认证
"""

import random
import string
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)


class PairingManager:
    """
    配对码管理器
    
    功能:
    - 生成 8 位配对码（大写，排除歧义字符）
    - 管理待处理配对请求
    - 管理已批准设备
    - 自动清理过期请求
    """
    
    # 可用字符：大写字母（排除 O、I）+ 数字（排除 0、1）
    AVAILABLE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化配对管理器
        
        Args:
            data_dir: 数据目录（用于持久化）
        """
        # 待处理的配对请求：code -> pairing_info
        self.pending_pairings: Dict[str, dict] = {}
        
        # 已批准的设备：device_id -> device_info
        self.approved_devices: Dict[str, dict] = {}
        
        # 配对码有效期（1 小时）
        self.pairing_ttl = timedelta(hours=1)
        
        # 每个频道待处理上限（3 个）
        self.max_pending_per_channel = 3
        
        # 数据目录
        self.data_dir = data_dir or os.path.join(
            os.path.expanduser('~'), 
            '.opc-agents', 
            'wechat'
        )
        
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 加载持久化数据
        self._load_data()
        
        logger.info(f"PairingManager initialized (data_dir={self.data_dir})")
    
    def generate_pairing_code(self) -> str:
        """
        生成 8 位配对码
        排除歧义字符：0O1I
        
        Returns:
            pairing_code: 8 位配对码
        """
        code = ''.join(random.choices(self.AVAILABLE_CHARS, k=8))
        logger.debug(f"Generated pairing code: {code}")
        return code
    
    def create_pairing_request(
        self, 
        channel: str, 
        device_id: str,
        device_info: dict
    ) -> str:
        """
        创建配对请求
        
        Args:
            channel: 渠道（wechat）
            device_id: 设备 ID
            device_info: 设备信息
            
        Returns:
            pairing_code: 配对码
            
        Raises:
            Exception: 当待处理请求超过上限时
        """
        # 检查待处理上限
        pending_count = sum(
            1 for p in self.pending_pairings.values() 
            if p['channel'] == channel
        )
        
        if pending_count >= self.max_pending_per_channel:
            logger.warning(
                f"Too many pending pairing requests for {channel}. "
                f"Max: {self.max_pending_per_channel}"
            )
            raise Exception(
                f"Too many pending pairing requests for {channel}. "
                f"Max: {self.max_pending_per_channel}"
            )
        
        # 生成配对码
        pairing_code = self.generate_pairing_code()
        
        # 存储配对请求
        self.pending_pairings[pairing_code] = {
            'channel': channel,
            'device_id': device_id,
            'device_info': device_info,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + self.pairing_ttl,
            'status': 'pending'
        }
        
        # 保存数据
        self._save_data()
        
        logger.info(
            f"Created pairing request: {pairing_code} "
            f"(device={device_id}, channel={channel}, "
            f"expires_at={self.pending_pairings[pairing_code]['expires_at']})"
        )
        
        return pairing_code
    
    def approve_pairing(self, pairing_code: str) -> Optional[dict]:
        """
        批准配对请求
        
        Args:
            pairing_code: 配对码
            
        Returns:
            device_info: 设备信息（如果成功）
            None: 如果配对码无效或已过期
        """
        if pairing_code not in self.pending_pairings:
            logger.warning(f"Pairing code not found: {pairing_code}")
            return None
        
        pairing = self.pending_pairings[pairing_code]
        
        # 检查是否过期
        if datetime.now() > pairing['expires_at']:
            logger.warning(f"Pairing code expired: {pairing_code}")
            del self.pending_pairings[pairing_code]
            self._save_data()
            return None
        
        # 移动到已批准列表
        device_id = pairing['device_id']
        device_info = pairing['device_info']
        
        self.approved_devices[device_id] = {
            **device_info,
            'device_id': device_id,
            'approved_at': datetime.now(),
            'channel': pairing['channel'],
            'pairing_code': pairing_code
        }
        
        # 删除待处理请求
        del self.pending_pairings[pairing_code]
        
        # 保存数据
        self._save_data()
        
        logger.info(f"Approved pairing: {device_id} (code={pairing_code})")
        return device_info
    
    def reject_pairing(self, pairing_code: str) -> bool:
        """
        拒绝配对请求
        
        Args:
            pairing_code: 配对码
            
        Returns:
            bool: 是否成功拒绝
        """
        if pairing_code in self.pending_pairings:
            del self.pending_pairings[pairing_code]
            self._save_data()
            logger.info(f"Rejected pairing: {pairing_code}")
            return True
        return False
    
    def list_pending(self, channel: Optional[str] = None) -> List[dict]:
        """
        列出待处理的配对请求
        
        Args:
            channel: 可选的频道过滤
            
        Returns:
            List[dict]: 待处理配对请求列表
        """
        pending = []
        for code, pairing in self.pending_pairings.items():
            if channel and pairing['channel'] != channel:
                continue
            
            # 计算剩余时间
            remaining = pairing['expires_at'] - datetime.now()
            
            pending.append({
                'code': code,
                'channel': pairing['channel'],
                'device_id': pairing['device_id'],
                'created_at': pairing['created_at'].isoformat(),
                'expires_at': pairing['expires_at'].isoformat(),
                'remaining_seconds': int(remaining.total_seconds()),
                'status': 'pending'
            })
        
        # 按剩余时间排序
        pending.sort(key=lambda x: x['remaining_seconds'], reverse=True)
        
        return pending
    
    def list_approved(self, channel: Optional[str] = None) -> List[dict]:
        """
        列出已批准的设备
        
        Args:
            channel: 可选的频道过滤
            
        Returns:
            List[dict]: 已批准设备列表
        """
        approved = []
        for device_id, info in self.approved_devices.items():
            if channel and info.get('channel') != channel:
                continue
            
            approved.append({
                'device_id': device_id,
                'channel': info.get('channel'),
                'approved_at': info.get('approved_at').isoformat(),
                'device_info': {
                    k: v for k, v in info.items() 
                    if k not in ['channel', 'approved_at', 'pairing_code']
                }
            })
        
        return approved
    
    def is_device_approved(self, device_id: str) -> bool:
        """
        检查设备是否已批准
        
        Args:
            device_id: 设备 ID
            
        Returns:
            bool: 是否已批准
        """
        return device_id in self.approved_devices
    
    def get_device_info(self, device_id: str) -> Optional[dict]:
        """
        获取设备信息
        
        Args:
            device_id: 设备 ID
            
        Returns:
            dict: 设备信息，如果不存在则返回 None
        """
        return self.approved_devices.get(device_id)
    
    def revoke_device(self, device_id: str) -> bool:
        """
        撤销已批准设备的访问权限
        
        Args:
            device_id: 设备 ID
            
        Returns:
            bool: 是否成功撤销
        """
        if device_id in self.approved_devices:
            del self.approved_devices[device_id]
            self._save_data()
            logger.info(f"Revoked device: {device_id}")
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """
        清理过期的配对请求
        
        Returns:
            int: 清理的数量
        """
        expired_codes = [
            code for code, pairing in self.pending_pairings.items()
            if datetime.now() > pairing['expires_at']
        ]
        
        for code in expired_codes:
            del self.pending_pairings[code]
            logger.info(f"Cleaned up expired pairing: {code}")
        
        if expired_codes:
            self._save_data()
        
        return len(expired_codes)
    
    def _save_data(self):
        """保存数据到文件"""
        try:
            # 保存待处理请求
            pending_file = os.path.join(self.data_dir, 'pending_pairings.json')
            pending_data = {}
            for code, pairing in self.pending_pairings.items():
                pending_data[code] = {
                    'channel': pairing['channel'],
                    'device_id': pairing['device_id'],
                    'device_info': pairing['device_info'],
                    'created_at': pairing['created_at'].isoformat(),
                    'expires_at': pairing['expires_at'].isoformat(),
                    'status': pairing['status']
                }
            
            with open(pending_file, 'w') as f:
                json.dump(pending_data, f, indent=2)
            
            # 保存已批准设备
            approved_file = os.path.join(self.data_dir, 'approved_devices.json')
            approved_data = {}
            for device_id, info in self.approved_devices.items():
                approved_data[device_id] = {
                    'channel': info.get('channel'),
                    'approved_at': info.get('approved_at').isoformat(),
                    'device_info': {
                        k: v for k, v in info.items() 
                        if k not in ['channel', 'approved_at', 'pairing_code']
                    }
                }
            
            with open(approved_file, 'w') as f:
                json.dump(approved_data, f, indent=2)
            
            logger.debug(f"Saved pairing data (pending={len(pending_data)}, approved={len(approved_data)})")
            
        except Exception as e:
            logger.error(f"Failed to save pairing data: {e}")
    
    def _load_data(self):
        """从文件加载数据"""
        try:
            # 加载待处理请求
            pending_file = os.path.join(self.data_dir, 'pending_pairings.json')
            if os.path.exists(pending_file):
                with open(pending_file, 'r') as f:
                    pending_data = json.load(f)
                
                for code, data in pending_data.items():
                    self.pending_pairings[code] = {
                        'channel': data['channel'],
                        'device_id': data['device_id'],
                        'device_info': data['device_info'],
                        'created_at': datetime.fromisoformat(data['created_at']),
                        'expires_at': datetime.fromisoformat(data['expires_at']),
                        'status': data['status']
                    }
                
                logger.debug(f"Loaded {len(self.pending_pairings)} pending pairings")
            
            # 加载已批准设备
            approved_file = os.path.join(self.data_dir, 'approved_devices.json')
            if os.path.exists(approved_file):
                with open(approved_file, 'r') as f:
                    approved_data = json.load(f)
                
                for device_id, data in approved_data.items():
                    self.approved_devices[device_id] = {
                        'channel': data.get('channel'),
                        'approved_at': datetime.fromisoformat(data.get('approved_at')),
                        **data.get('device_info', {})
                    }
                
                logger.debug(f"Loaded {len(self.approved_devices)} approved devices")
            
            # 清理过期的待处理请求
            expired_count = self.cleanup_expired()
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired pairings on load")
            
        except Exception as e:
            logger.error(f"Failed to load pairing data: {e}")
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            'pending_count': len(self.pending_pairings),
            'approved_count': len(self.approved_devices),
            'expired_count': sum(
                1 for p in self.pending_pairings.values()
                if datetime.now() > p['expires_at']
            )
        }


# 全局单例
pairing_manager = PairingManager()
