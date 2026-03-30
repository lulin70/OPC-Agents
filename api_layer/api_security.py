#!/usr/bin/env python3
"""
API安全模块

实现API安全认证功能。
"""

import logging
import time
import hashlib
import jwt
from flask import request, jsonify
from typing import Dict, Any, Optional

class APISecurity:
    """API安全认证类"""
    
    def __init__(self, secret_key: str = None, algorithm: str = 'HS256'):
        """
        初始化API安全认证
        
        Args:
            secret_key: JWT密钥
            algorithm: JWT算法
        """
        self.logger = logging.getLogger('OPC-Agents.APISecurity')
        # 从环境变量获取密钥，优先使用环境变量
        import os
        self.secret_key = secret_key or os.environ.get('JWT_SECRET_KEY', 'opc-agents-secret-key')
        self.algorithm = algorithm
        self.blacklist = set()
        # 加载持久化的黑名单
        self._load_blacklist()
    
    def generate_token(self, user_id: str, role: str = 'user', expires_in: int = 3600) -> str:
        """
        生成JWT令牌
        
        Args:
            user_id: 用户ID
            role: 用户角色
            expires_in: 过期时间（秒）
            
        Returns:
            JWT令牌
        """
        payload = {
            'user_id': user_id,
            'role': role,
            'exp': time.time() + expires_in,
            'iat': time.time()
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        self.logger.info(f"生成令牌: {user_id}")
        return token
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        验证JWT令牌
        
        Args:
            token: JWT令牌
            
        Returns:
            令牌载荷，如果验证失败则返回None
        """
        try:
            # 检查令牌是否在黑名单中
            if token in self.blacklist:
                self.logger.warning("令牌已被注销")
                return None
            
            # 验证令牌
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # 检查令牌是否过期
            if payload['exp'] < time.time():
                self.logger.warning("令牌已过期")
                return None
            
            return payload
        except jwt.InvalidTokenError as e:
            self.logger.error(f"令牌验证失败: {e}")
            return None
    
    def logout(self, token: str) -> bool:
        """
        注销令牌
        
        Args:
            token: JWT令牌
            
        Returns:
            是否成功注销
        """
        try:
            # 验证令牌是否有效
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # 将令牌加入黑名单
            self.blacklist.add(token)
            # 持久化黑名单
            self._save_blacklist()
            self.logger.info(f"注销令牌: {payload['user_id']}")
            return True
        except jwt.InvalidTokenError:
            self.logger.error("注销无效令牌")
            return False
    
    def _save_blacklist(self):
        """
        保存黑名单到文件
        """
        try:
            import json
            import os
            # 确保目录存在
            os.makedirs('security', exist_ok=True)
            # 保存黑名单
            with open('security/token_blacklist.json', 'w', encoding='utf-8') as f:
                json.dump(list(self.blacklist), f)
        except Exception as e:
            self.logger.error(f"保存黑名单失败: {e}")
    
    def _load_blacklist(self):
        """
        从文件加载黑名单
        """
        try:
            import json
            import os
            if os.path.exists('security/token_blacklist.json'):
                with open('security/token_blacklist.json', 'r', encoding='utf-8') as f:
                    self.blacklist = set(json.load(f))
        except Exception as e:
            self.logger.error(f"加载黑名单失败: {e}")
            self.blacklist = set()
    
    def require_auth(self, request):
        """
        要求认证的中间件
        
        Args:
            request: Flask请求对象
            
        Returns:
            如果认证失败则返回错误响应，否则返回None
        """
        # 获取Authorization头
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': '缺少认证令牌'}), 401
        
        # 提取令牌
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        else:
            return jsonify({'error': '认证格式错误'}), 401
        
        # 验证令牌
        payload = self.verify_token(token)
        if not payload:
            return jsonify({'error': '无效的认证令牌'}), 401
        
        # 将用户信息添加到请求上下文
        request.user_id = payload['user_id']
        request.user_role = payload['role']
        
        return None
    
    def require_role(self, roles: list):
        """
        要求特定角色的中间件
        
        Args:
            roles: 允许的角色列表
            
        Returns:
            中间件函数
        """
        def middleware(request):
            # 先进行认证
            auth_result = self.require_auth(request)
            if auth_result is not None:
                return auth_result
            
            # 检查角色
            if request.user_role not in roles:
                return jsonify({'error': '权限不足'}), 403
            
            return None
        
        return middleware
    
    def generate_api_key(self, user_id: str) -> str:
        """
        生成API密钥
        
        Args:
            user_id: 用户ID
            
        Returns:
            API密钥
        """
        # 生成基于时间戳和用户ID的API密钥
        timestamp = str(int(time.time()))
        data = f"{user_id}:{timestamp}:{self.secret_key}"
        api_key = hashlib.sha256(data.encode()).hexdigest()
        
        self.logger.info(f"生成API密钥: {user_id}")
        return api_key
    
    def verify_api_key(self, api_key: str) -> bool:
        """
        验证API密钥
        
        Args:
            api_key: API密钥
            
        Returns:
            是否有效
        """
        # 检查API密钥格式
        if len(api_key) != 64:
            return False
        
        try:
            # 尝试将API密钥解析为十六进制
            int(api_key, 16)
        except ValueError:
            return False
        
        # 可以从配置文件或数据库中加载有效的API密钥
        # 这里简单实现为检查是否在预定义的密钥列表中
        import os
        valid_api_keys = os.environ.get('VALID_API_KEYS', '').split(',')
        if valid_api_keys and api_key not in valid_api_keys:
            return False
        
        return True
    
    def api_key_auth(self, request):
        """
        API密钥认证中间件
        
        Args:
            request: Flask请求对象
            
        Returns:
            如果认证失败则返回错误响应，否则返回None
        """
        # 获取API-Key头
        api_key = request.headers.get('API-Key')
        
        if not api_key:
            return jsonify({'error': '缺少API密钥'}), 401
        
        # 验证API密钥
        if not self.verify_api_key(api_key):
            return jsonify({'error': '无效的API密钥'}), 401
        
        return None