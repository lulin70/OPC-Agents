import io

from PIL import Image, ImageDraw, ImageFont


class ImageExporter:
    def export(self, data, template=None, **opts) -> bytes:
        width = opts.get("width", 1080)
        height = opts.get("height", 1080)
        bg_color = opts.get("bg_color", (255, 248, 220))
        text_color = opts.get("text_color", (33, 33, 33))

        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 36)
            font_normal = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_normal = ImageFont.load_default()

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
