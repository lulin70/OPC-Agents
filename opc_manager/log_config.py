#!/usr/bin/env python3
"""
Log configuration module for OPC-Agents
"""

import os
import logging

class LogConfig:
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 日志文件名
        self.log_file = os.path.join(self.log_dir, f"opc_agents_{'debug' if debug_mode else 'normal'}.log")
        
        # 配置根日志
        log_level = logging.DEBUG if debug_mode else logging.INFO
        
        # 创建logger
        self.logger = logging.getLogger("OPC-Agents")
        self.logger.setLevel(log_level)
        
        # 清除现有的处理器
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        
        # 设置格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

# 全局日志配置
log_config = LogConfig(debug_mode=False)