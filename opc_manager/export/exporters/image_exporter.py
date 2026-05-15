import io
import os
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

FONT_FALLBACK_LIST: List[Tuple[str, int]] = [
    ("/System/Library/Fonts/PingFang.ttc", 36),
    ("/System/Library/Fonts/Helvetica.ttc", 36),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36),
]

FONT_FALLBACK_NORMAL: List[Tuple[str, int]] = [
    ("/System/Library/Fonts/PingFang.ttc", 24),
    ("/System/Library/Fonts/Helvetica.ttc", 24),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24),
]


class ImageExporter:
    def _load_font(self, font_list: List[Tuple[str, int]], default_size: int):
        for font_path, size in font_list:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError):
                    continue
        return ImageFont.load_default()

    def export(self, data, template=None, **opts) -> bytes:
        width = opts.get("width", 1080)
        height = opts.get("height", 1080)
        bg_color = opts.get("bg_color", (255, 248, 220))
        text_color = opts.get("text_color", (33, 33, 33))

        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        font_large = self._load_font(FONT_FALLBACK_LIST, 36)
        font_normal = self._load_font(FONT_FALLBACK_NORMAL, 24)

        title = data.metadata.get("title", "")
        if title:
            bbox = draw.textbbox((0, 0), title, font=font_large)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) / 2, 80), title, fill=text_color, font=font_large)

        y = 160
        for line in data.content.split('\n')[:20]:
            if line.strip():
                draw.text((60, y), line.strip(), fill=text_color, font=font_normal)
                y += 40
                if y > height - 60:
                    break

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
