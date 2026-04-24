"""输入验证层 - 使用Pydantic进行数据验证"""

from pydantic import BaseModel, Field, validator, ValidationError
from typing import Optional, List, Dict, Any
from enum import Enum
import re


class BusinessType(str, Enum):
    """业务类型枚举"""

    CONTENT_CREATOR = "content_creator"
    DIGITAL_PRODUCT = "digital_product"
    AI_TOOL_BUILDER = "ai_tool_builder"
    CONSULTANT = "consultant"
    ECOMMERCE = "ecommerce"
    CREATIVE_WORK = "creative_work"
    UNKNOWN = "unknown"


class TaskRequest(BaseModel):
    """任务请求验证模型"""

    user_input: str = Field(..., min_length=1, max_length=10000, description="用户输入")
    business_type: Optional[BusinessType] = Field(None, description="业务类型")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="上下文信息"
    )

    @validator("user_input")
    def validate_user_input(cls, v):
        """验证用户输入"""
        # 移除前后空白
        v = v.strip()

        # 检查是否为空
        if not v:
            raise ValueError("用户输入不能为空")

        # 检查是否包含恶意脚本
        dangerous_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"eval\s*\(",
            r"exec\s*\(",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("输入包含潜在的恶意内容")

        return v

    class Config:
        use_enum_values = True


class AgentConfig(BaseModel):
    """Agent配置验证模型"""

    agent_id: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    display_name: str = Field(..., min_length=1, max_length=200)
    expertise_tags: List[str] = Field(default_factory=list, max_items=20)
    style_overrides: Optional[Dict[str, str]] = Field(default_factory=dict)

    @validator("expertise_tags")
    def validate_expertise_tags(cls, v):
        """验证专业标签"""
        if not v:
            return v

        # 检查每个标签长度
        for tag in v:
            if len(tag) > 50:
                raise ValueError(f"专业标签过长: {tag}")
            if not tag.strip():
                raise ValueError("专业标签不能为空")

        return [tag.strip() for tag in v]

    @validator("agent_id")
    def validate_agent_id(cls, v):
        """验证Agent ID"""
        if v.startswith("_") or v.endswith("_"):
            raise ValueError("Agent ID不能以下划线开头或结尾")
        return v


class LLMRequest(BaseModel):
    """LLM请求验证模型"""

    prompt: str = Field(..., min_length=1, max_length=50000)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    max_tokens: int = Field(default=500, ge=1, le=8000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    @validator("prompt", "system_prompt")
    def validate_prompts(cls, v):
        """验证提示词"""
        if v is None:
            return v

        v = v.strip()

        # 检查SQL注入模式
        sql_patterns = [
            r"('\s*(or|and)\s*'?\d)",
            r"(union\s+select)",
            r"(drop\s+table)",
            r"(insert\s+into)",
            r"(delete\s+from)",
        ]
        for pattern in sql_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("输入包含潜在的SQL注入模式")

        return v


class SearchQuery(BaseModel):
    """搜索查询验证模型"""

    query: str = Field(..., min_length=1, max_length=500)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @validator("query")
    def validate_query(cls, v):
        """验证搜索查询"""
        v = v.strip()

        if not v:
            raise ValueError("搜索查询不能为空")

        # 检查特殊字符
        if re.search(r"[<>{}]", v):
            raise ValueError("搜索查询包含非法字符")

        return v


class FileUpload(BaseModel):
    """文件上传验证模型"""

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., pattern=r"^[a-zA-Z0-9]+/[a-zA-Z0-9\-\+\.]+$")
    size_bytes: int = Field(..., ge=1, le=10_000_000)  # 最大10MB

    @validator("filename")
    def validate_filename(cls, v):
        """验证文件名"""
        # 移除路径分隔符
        v = v.replace("/", "").replace("\\", "").replace("..", "")

        # 检查文件扩展名
        allowed_extensions = {
            ".txt",
            ".md",
            ".json",
            ".yaml",
            ".yml",
            ".pdf",
            ".doc",
            ".docx",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
        }

        ext = "." + v.rsplit(".", 1)[-1].lower() if "." in v else ""
        if ext and ext not in allowed_extensions:
            raise ValueError(f"不支持的文件类型: {ext}")

        return v

    @validator("content_type")
    def validate_content_type(cls, v):
        """验证内容类型"""
        allowed_types = {
            "text/plain",
            "text/markdown",
            "application/json",
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "image/jpeg",
            "image/png",
            "image/gif",
        }

        if v not in allowed_types:
            raise ValueError(f"不支持的内容类型: {v}")

        return v


def validate_input(model_class: type[BaseModel], data: dict) -> BaseModel:
    """
    验证输入数据

    Args:
        model_class: Pydantic模型类
        data: 待验证的数据

    Returns:
        验证后的模型实例

    Raises:
        ValidationError: 验证失败时抛出
    """
    try:
        return model_class(**data)
    except ValidationError as e:
        # 格式化错误信息
        errors = []
        for error in e.errors():
            field = ".".join(str(x) for x in error["loc"])
            message = error["msg"]
            errors.append(f"{field}: {message}")

        raise ValueError(f"输入验证失败: {', '.join(errors)}")


def sanitize_html(text: str) -> str:
    """
    清理HTML内容，防止XSS攻击

    Args:
        text: 待清理的文本

    Returns:
        清理后的文本
    """
    if not text:
        return text

    # 转义HTML特殊字符（注意顺序：&必须最先处理）
    replacements = [
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&#x27;"),
    ]

    for char, escaped in replacements:
        text = text.replace(char, escaped)

    return text


def validate_json_structure(
    data: Any, max_depth: int = 10, current_depth: int = 0
) -> bool:
    """
    验证JSON结构深度，防止嵌套过深导致的DoS攻击

    Args:
        data: JSON数据
        max_depth: 最大深度
        current_depth: 当前深度

    Returns:
        是否有效

    Raises:
        ValueError: 深度超过限制时抛出
    """
    if current_depth > max_depth:
        raise ValueError(f"JSON嵌套深度超过限制: {max_depth}")

    if isinstance(data, dict):
        for value in data.values():
            validate_json_structure(value, max_depth, current_depth + 1)
    elif isinstance(data, list):
        for item in data:
            validate_json_structure(item, max_depth, current_depth + 1)

    return True


# 导出验证模型和函数
__all__ = [
    "BusinessType",
    "TaskRequest",
    "AgentConfig",
    "LLMRequest",
    "SearchQuery",
    "FileUpload",
    "validate_input",
    "sanitize_html",
    "validate_json_structure",
]
