"""
示例插件: 文本摘要生成器

功能: 将长文本摘要为指定字数
权限: 无需特殊权限（纯计算）
"""


def initialize(config):
    _config = config


def summarize(text="", max_length=200):
    if not text:
        return {"error": "No text provided"}
    if len(text) <= max_length:
        return {"summary": text, "original_length": len(text), "summary_length": len(text)}
    sentences = text.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n").split("\n")
    sentences = [s.strip() for s in sentences if s.strip()]
    summary = ""
    for s in sentences:
        if len(summary) + len(s) <= max_length:
            summary += s
        else:
            break
    if not summary:
        summary = text[:max_length] + "..."
    return {"summary": summary, "original_length": len(text), "summary_length": len(summary)}


def shutdown():
    pass
