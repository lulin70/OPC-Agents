"""
二维码生成器 - 微信配对二维码生成

支持生成 Base64 PNG 和 ASCII 二维码
"""

import base64
import io
import json
import logging
from typing import Optional

try:
    import qrcode
    from PIL import Image
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    qrcode = None
    Image = None

logger = logging.getLogger(__name__)


class QRCodeGenerator:
    """
    二维码生成器
    
    功能:
    - 生成 Base64 PNG 二维码（Web 界面用）
    - 生成 ASCII 二维码（终端用）
    - 支持自定义配置
    """
    
    def __init__(self):
        """初始化二维码生成器"""
        if not QR_AVAILABLE:
            logger.warning(
                "qrcode library not available. "
                "Install with: pip install qrcode[pil]"
            )
        
        # 默认配置
        self.default_config = {
            'version': 1,
            'error_correction': qrcode.constants.ERROR_CORRECT_L if QR_AVAILABLE else None,
            'box_size': 10,
            'border': 4,
        }
        
        logger.info("QRCodeGenerator initialized")
    
    def generate_pairing_qr(
        self, 
        pairing_code: str,
        websocket_url: str,
        device_id: str,
        fill_color: str = "black",
        back_color: str = "white"
    ) -> str:
        """
        生成配对二维码（Base64 PNG）
        
        Args:
            pairing_code: 8 位配对码
            websocket_url: WebSocket 连接地址
            device_id: 设备 ID
            fill_color: 二维码颜色
            back_color: 背景颜色
            
        Returns:
            base64_qr: Base64 编码的 PNG 图片（data:image/png;base64,...）
            
        Raises:
            ImportError: 如果 qrcode 库未安装
        """
        if not QR_AVAILABLE:
            raise ImportError(
                "qrcode library is required. Install with: pip install qrcode[pil]"
            )
        
        # 构建连接信息（JSON 格式）
        connection_info = {
            'type': 'pairing',
            'code': pairing_code,
            'url': websocket_url,
            'device_id': device_id,
            'version': '1.0'
        }
        
        # 转换为 JSON 字符串
        qr_data = json.dumps(connection_info)
        
        # 创建二维码对象
        qr = qrcode.QRCode(
            version=self.default_config['version'],
            error_correction=self.default_config['error_correction'],
            box_size=self.default_config['box_size'],
            border=self.default_config['border'],
        )
        
        # 添加数据
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # 创建图片
        img = qr.make_image(
            fill_color=fill_color, 
            back_color=back_color
        )
        
        # 转换为 Base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        base64_qr = base64.b64encode(buffer.read()).decode('utf-8')
        
        logger.info(
            f"Generated pairing QR code (code={pairing_code}, "
            f"size={img.size[0]}x{img.size[1]})"
        )
        
        return f"data:image/png;base64,{base64_qr}"
    
    def generate_simple_qr(
        self,
        data: str,
        fill_color: str = "black",
        back_color: str = "white"
    ) -> str:
        """
        生成简单二维码（Base64 PNG）
        
        Args:
            data: 要编码的数据
            fill_color: 二维码颜色
            back_color: 背景颜色
            
        Returns:
            base64_qr: Base64 编码的 PNG 图片
        """
        if not QR_AVAILABLE:
            raise ImportError(
                "qrcode library is required. Install with: pip install qrcode[pil]"
            )
        
        # 创建二维码对象
        qr = qrcode.QRCode(
            version=self.default_config['version'],
            error_correction=self.default_config['error_correction'],
            box_size=self.default_config['box_size'],
            border=self.default_config['border'],
        )
        
        # 添加数据
        qr.add_data(data)
        qr.make(fit=True)
        
        # 创建图片
        img = qr.make_image(
            fill_color=fill_color, 
            back_color=back_color
        )
        
        # 转换为 Base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        base64_qr = base64.b64encode(buffer.read()).decode('utf-8')
        
        logger.info(f"Generated simple QR code (size={img.size[0]}x{img.size[1]})")
        
        return f"data:image/png;base64,{base64_qr}"
    
    def generate_ascii_qr(
        self, 
        data: str,
        invert: bool = True
    ) -> str:
        """
        生成 ASCII 二维码（终端显示用）
        
        Args:
            data: 要编码的数据
            invert: 是否反转颜色
            
        Returns:
            ascii_qr: ASCII 字符组成的二维码
        """
        if not QR_AVAILABLE:
            raise ImportError(
                "qrcode library is required. Install with: pip install qrcode[pil]"
            )
        
        # 创建二维码对象
        qr = qrcode.QRCode(
            version=self.default_config['version'],
            error_correction=self.default_config['error_correction'],
            box_size=self.default_config['box_size'],
            border=self.default_config['border'],
        )
        
        # 添加数据
        qr.add_data(data)
        qr.make(fit=True)
        
        # 生成 ASCII
        buffer = io.StringIO()
        qr.print_ascii(
            out=buffer, 
            invert=invert,
            tty=False
        )
        ascii_qr = buffer.getvalue()
        
        logger.info(f"Generated ASCII QR code (lines={len(ascii_qr.splitlines())})")
        
        return ascii_qr
    
    def generate_pairing_code_display(
        self,
        pairing_code: str
    ) -> str:
        """
        生成配对码 ASCII 展示
        
        Args:
            pairing_code: 8 位配对码
            
        Returns:
            ascii_display: ASCII 字符组成的展示
        """
        # 使用 ASCII 二维码
        ascii_qr = self.generate_ascii_qr(pairing_code)
        
        # 添加标题
        display = f"""
╔{'═' * 40}╗
║  配对码：{pairing_code}{' ' * (28 - len(pairing_code))}║
╠{'═' * 40}╣
║  请扫描上方二维码完成绑定          ║
║  或使用配对码进行命令行绑定        ║
╚{'═' * 40}╝

{ascii_qr}

配对码：{pairing_code}

提示：
- 二维码有效期 1 小时
- 使用微信"扫一扫"扫描二维码
- 或在命令行输入配对码批准
"""
        
        return display


# 全局单例
qr_generator = QRCodeGenerator()
