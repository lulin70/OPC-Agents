"""
通知管理器
实现多渠道通知功能，让用户在离开页面时也能收到任务完成提醒
"""

import smtplib
import requests
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading


class NotificationManager:
    """通知管理器，支持多渠道通知"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化通知管理器
        
        Args:
            config: 通知配置
        """
        self.config = config or {}
        self.logger = logging.getLogger("OPC-Agents.Notification")
        self.notification_history = []
        
        # 通知渠道配置
        self.email_config = self.config.get('email', {})
        self.wechat_config = self.config.get('wechat', {})
        self.dingtalk_config = self.config.get('dingtalk', {})
        self.console_config = self.config.get('console', {'enabled': True})
        
        self.logger.info("通知管理器初始化完成")
    
    def notify_task_complete(self, task_id: str, task_name: str, user: Dict, 
                            channels: Optional[List[str]] = None) -> Dict:
        """
        通知用户任务完成
        
        Args:
            task_id: 任务 ID
            task_name: 任务名称
            user: 用户信息
            channels: 通知渠道列表，默认使用用户配置
            
        Returns:
            通知结果
        """
        channels = channels or user.get('notification_channels', ['console'])
        
        results = {
            'task_id': task_id,
            'task_name': task_name,
            'timestamp': datetime.now().isoformat(),
            'channels': {},
            'success': False
        }
        
        # 并行发送所有渠道
        threads = []
        
        for channel in channels:
            if channel == 'email' and self.email_config.get('enabled'):
                thread = threading.Thread(
                    target=self._send_email_notification,
                    args=(task_id, task_name, user, results)
                )
                threads.append(thread)
                thread.start()
            
            elif channel == 'wechat' and self.wechat_config.get('enabled'):
                thread = threading.Thread(
                    target=self._send_wechat_notification,
                    args=(task_id, task_name, user, results)
                )
                threads.append(thread)
                thread.start()
            
            elif channel == 'dingtalk' and self.dingtalk_config.get('enabled'):
                thread = threading.Thread(
                    target=self._send_dingtalk_notification,
                    args=(task_id, task_name, user, results)
                )
                threads.append(thread)
                thread.start()
            
            elif channel == 'console':
                self._send_console_notification(task_id, task_name, user, results)
        
        # 等待所有异步通知完成
        for thread in threads:
            thread.join(timeout=10)  # 最多等待 10 秒
        
        # 检查是否有成功的渠道
        results['success'] = any(
            result.get('success', False) 
            for result in results['channels'].values()
        )
        
        # 记录历史
        self.notification_history.append(results)
        
        return results
    
    def notify_task_failed(self, task_id: str, task_name: str, error: str, 
                          user: Dict, suggestion: Optional[str] = None) -> Dict:
        """
        通知用户任务失败
        
        Args:
            task_id: 任务 ID
            task_name: 任务名称
            error: 错误信息
            user: 用户信息
            suggestion: 处理建议
            
        Returns:
            通知结果
        """
        channels = user.get('notification_channels', ['console'])
        
        results = {
            'task_id': task_id,
            'task_name': task_name,
            'error': error,
            'suggestion': suggestion,
            'timestamp': datetime.now().isoformat(),
            'channels': {},
            'success': False
        }
        
        for channel in channels:
            if channel == 'email' and self.email_config.get('enabled'):
                self._send_email_failure(task_id, task_name, error, suggestion, user, results)
            elif channel == 'wechat' and self.wechat_config.get('enabled'):
                self._send_wechat_failure(task_id, task_name, error, suggestion, user, results)
            elif channel == 'dingtalk' and self.dingtalk_config.get('enabled'):
                self._send_dingtalk_failure(task_id, task_name, error, suggestion, user, results)
            elif channel == 'console':
                self._send_console_failure(task_id, task_name, error, suggestion, user, results)
        
        results['success'] = any(
            result.get('success', False) 
            for result in results['channels'].values()
        )
        
        self.notification_history.append(results)
        return results
    
    def _send_email_notification(self, task_id: str, task_name: str, 
                                user: Dict, results: Dict):
        """发送邮件通知"""
        try:
            if not self.email_config.get('enabled'):
                return
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.email_config['smtp_username']
            msg['To'] = user['email']
            msg['Subject'] = f"✅ 任务完成通知 - {task_name}"
            
            # 邮件内容
            html = f"""
            <html>
            <body>
                <h2>✅ 任务完成</h2>
                <p>您的任务已完成：</p>
                <ul>
                    <li><strong>任务 ID:</strong> {task_id}</li>
                    <li><strong>任务名称:</strong> {task_name}</li>
                    <li><strong>完成时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                </ul>
                <p>您可以登录系统查看详细结果。</p>
                <br>
                <p style="color: #666; font-size: 12px;">OPC-Agents 自动通知</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html, 'html', 'utf-8'))
            
            # 发送邮件
            server = smtplib.SMTP(
                self.email_config['smtp_server'],
                self.email_config['smtp_port']
            )
            server.starttls()
            server.login(
                self.email_config['smtp_username'],
                self.email_config['smtp_password']
            )
            server.send_message(msg)
            server.quit()
            
            results['channels']['email'] = {
                'success': True,
                'channel': 'email',
                'recipient': user['email']
            }
            
            self.logger.info(f"邮件通知发送成功：{user['email']}")
            
        except Exception as e:
            self.logger.error(f"邮件通知发送失败：{e}")
            results['channels']['email'] = {
                'success': False,
                'channel': 'email',
                'error': str(e)
            }
    
    def _send_wechat_notification(self, task_id: str, task_name: str,
                                 user: Dict, results: Dict):
        """发送微信通知（通过企业微信）"""
        try:
            if not self.wechat_config.get('enabled'):
                return
            
            webhook_url = self.wechat_config.get('webhook_url')
            if not webhook_url:
                return
            
            # 企业微信消息格式
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"""## ✅ 任务完成通知 
**任务 ID**: {task_id}
**任务名称**: {task_name}
**完成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

您可以登录系统查看详细结果。"""
                }
            }
            
            response = requests.post(webhook_url, json=data, timeout=10)
            response.raise_for_status()
            
            result_data = response.json()
            if result_data.get('errcode') == 0:
                results['channels']['wechat'] = {
                    'success': True,
                    'channel': 'wechat',
                    'recipient': user.get('wechat_id', 'unknown')
                }
                self.logger.info("微信通知发送成功")
            else:
                raise Exception(f"企业微信返回错误：{result_data}")
                
        except Exception as e:
            self.logger.error(f"微信通知发送失败：{e}")
            results['channels']['wechat'] = {
                'success': False,
                'channel': 'wechat',
                'error': str(e)
            }
    
    def _send_dingtalk_notification(self, task_id: str, task_name: str,
                                   user: Dict, results: Dict):
        """发送钉钉通知"""
        try:
            if not self.dingtalk_config.get('enabled'):
                return
            
            webhook_url = self.dingtalk_config.get('webhook_url')
            if not webhook_url:
                return
            
            # 钉钉消息格式
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "任务完成通知",
                    "text": f"""## ✅ 任务完成通知 
- **任务 ID**: {task_id}
- **任务名称**: {task_name}
- **完成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

您可以登录系统查看详细结果。"""
                },
                "at": {
                    "isAtAll": True
                }
            }
            
            response = requests.post(webhook_url, json=data, timeout=10)
            response.raise_for_status()
            
            result_data = response.json()
            if result_data.get('errcode') == 0:
                results['channels']['dingtalk'] = {
                    'success': True,
                    'channel': 'dingtalk',
                    'recipient': user.get('dingtalk_id', 'unknown')
                }
                self.logger.info("钉钉通知发送成功")
            else:
                raise Exception(f"钉钉返回错误：{result_data}")
                
        except Exception as e:
            self.logger.error(f"钉钉通知发送失败：{e}")
            results['channels']['dingtalk'] = {
                'success': False,
                'channel': 'dingtalk',
                'error': str(e)
            }
    
    def _send_console_notification(self, task_id: str, task_name: str,
                                  user: Dict, results: Dict):
        """发送控制台通知"""
        print(f"\n{'='*60}")
        print(f"✅ 任务完成通知")
        print(f"{'='*60}")
        print(f"任务 ID: {task_id}")
        print(f"任务名称：{task_name}")
        print(f"完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        results['channels']['console'] = {
            'success': True,
            'channel': 'console'
        }
    
    def _send_email_failure(self, task_id: str, task_name: str,
                           error: str, suggestion: Optional[str],
                           user: Dict, results: Dict):
        """发送失败通知邮件"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['smtp_username']
            msg['To'] = user['email']
            msg['Subject'] = f"❌ 任务失败通知 - {task_name}"
            
            html = f"""
            <html>
            <body>
                <h2>❌ 任务失败</h2>
                <p>您的任务执行失败：</p>
                <ul>
                    <li><strong>任务 ID:</strong> {task_id}</li>
                    <li><strong>任务名称:</strong> {task_name}</li>
                    <li><strong>错误信息:</strong> {error}</li>
                </ul>
                {'<p><strong>处理建议:</strong> ' + suggestion + '</p>' if suggestion else ''}
                <p>请检查配置或联系管理员。</p>
                <br>
                <p style="color: #666; font-size: 12px;">OPC-Agents 自动通知</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html, 'html', 'utf-8'))
            
            server = smtplib.SMTP(
                self.email_config['smtp_server'],
                self.email_config['smtp_port']
            )
            server.starttls()
            server.login(
                self.email_config['smtp_username'],
                self.email_config['smtp_password']
            )
            server.send_message(msg)
            server.quit()
            
            results['channels']['email'] = {
                'success': True,
                'channel': 'email',
                'recipient': user['email']
            }
            
        except Exception as e:
            results['channels']['email'] = {
                'success': False,
                'channel': 'email',
                'error': str(e)
            }
    
    def _send_wechat_failure(self, task_id: str, task_name: str,
                            error: str, suggestion: Optional[str],
                            user: Dict, results: Dict):
        """发送微信失败通知"""
        try:
            webhook_url = self.wechat_config.get('webhook_url')
            if not webhook_url:
                return
            
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"""## ❌ 任务失败通知 
**任务 ID**: {task_id}
**任务名称**: {task_name}
**错误信息**: {error}
{'**处理建议**: ' + suggestion if suggestion else ''}"""
                }
            }
            
            response = requests.post(webhook_url, json=data, timeout=10)
            response.raise_for_status()
            
            if response.json().get('errcode') == 0:
                results['channels']['wechat'] = {'success': True, 'channel': 'wechat'}
            else:
                raise Exception("企业微信返回错误")
                
        except Exception as e:
            results['channels']['wechat'] = {
                'success': False,
                'channel': 'wechat',
                'error': str(e)
            }
    
    def _send_dingtalk_failure(self, task_id: str, task_name: str,
                              error: str, suggestion: Optional[str],
                              user: Dict, results: Dict):
        """发送钉钉失败通知"""
        try:
            webhook_url = self.dingtalk_config.get('webhook_url')
            if not webhook_url:
                return
            
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "任务失败通知",
                    "text": f"""## ❌ 任务失败通知 
- **任务 ID**: {task_id}
- **任务名称**: {task_name}
- **错误信息**: {error}
{'- **处理建议**: ' + suggestion if suggestion else ''}"""
                },
                "at": {"isAtAll": True}
            }
            
            response = requests.post(webhook_url, json=data, timeout=10)
            response.raise_for_status()
            
            if response.json().get('errcode') == 0:
                results['channels']['dingtalk'] = {'success': True, 'channel': 'dingtalk'}
            else:
                raise Exception("钉钉返回错误")
                
        except Exception as e:
            results['channels']['dingtalk'] = {
                'success': False,
                'channel': 'dingtalk',
                'error': str(e)
            }
    
    def _send_console_failure(self, task_id: str, task_name: str,
                             error: str, suggestion: Optional[str],
                             user: Dict, results: Dict):
        """发送控制台失败通知"""
        print(f"\n{'='*60}")
        print(f"❌ 任务失败通知")
        print(f"{'='*60}")
        print(f"任务 ID: {task_id}")
        print(f"任务名称：{task_name}")
        print(f"错误信息：{error}")
        if suggestion:
            print(f"处理建议：{suggestion}")
        print(f"{'='*60}\n")
        
        results['channels']['console'] = {
            'success': True,
            'channel': 'console'
        }
    
    def get_notification_history(self, limit: int = 50) -> List[Dict]:
        """获取通知历史"""
        return self.notification_history[-limit:]
    
    def test_notification(self, user: Dict, channels: List[str]) -> Dict:
        """测试通知渠道"""
        return self.notify_task_complete(
            task_id='test_001',
            task_name='测试任务',
            user=user,
            channels=channels
        )


# 使用示例
if __name__ == '__main__':
    # 配置
    config = {
        'email': {
            'enabled': True,
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_username': 'noreply@example.com',
            'smtp_password': 'password'
        },
        'wechat': {
            'enabled': True,
            'webhook_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx'
        },
        'dingtalk': {
            'enabled': True,
            'webhook_url': 'https://oapi.dingtalk.com/robot/send?access_token=xxx'
        },
        'console': {
            'enabled': True
        }
    }
    
    # 创建通知管理器
    notifier = NotificationManager(config)
    
    # 测试用户
    user = {
        'name': '张三',
        'email': 'zhangsan@example.com',
        'wechat_id': 'zhangsan',
        'dingtalk_id': 'zhangsan',
        'notification_channels': ['console', 'email', 'wechat', 'dingtalk']
    }
    
    # 测试通知
    print("\n[测试] 任务完成通知")
    result = notifier.notify_task_complete(
        task_id='task_001',
        task_name='分析 100 份 PDF 文档',
        user=user
    )
    
    print(f"\n通知结果：{result}")
    print(f"各渠道状态:")
    for channel, status in result['channels'].items():
        print(f"  - {channel}: {'✅' if status.get('success') else '❌'}")
