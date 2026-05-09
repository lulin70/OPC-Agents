"""
示例插件: 数据格式转换器

功能: JSON↔CSV↔Markdown表格互转
权限: 无需特殊权限（纯计算）
"""


def initialize(config):
    _config = config


def json_to_table(data=None):
    if not data or not isinstance(data, list):
        return {"error": "Expected list of dicts"}
    if not data:
        return {"table": "", "rows": 0}
    headers = list(data[0].keys())
    md_lines = ["| " + " | ".join(headers) + " |"]
    md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in data:
        md_lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    table = "\n".join(md_lines)
    return {"table": table, "rows": len(data), "columns": len(headers)}


def shutdown():
    pass
