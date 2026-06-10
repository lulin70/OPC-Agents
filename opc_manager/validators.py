"""Input Validation Layer - Using Pydantic V2 for data validation"""

from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationError
from typing import Optional, List, Dict, Any
from opc_manager.business_types import BusinessType
import re


class TaskRequest(BaseModel):
    """Task request validation model"""

    model_config = ConfigDict(use_enum_values=True)

    user_input: str = Field(
        ..., min_length=1, max_length=10000, description="User input"
    )
    business_type: Optional[BusinessType] = Field(None, description="Business type")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Context information"
    )

    @field_validator("user_input")
    @classmethod
    def validate_user_input(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("用户输入不能为空")
        dangerous_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"data:text/html",
            r"on\w+\s*=",
            r"on\w+=",
            r"eval\s*\(",
            r"exec\s*\(",
            r"<\s*iframe",
            r"<\s*object",
            r"<\s*embed",
            r"<\s*svg[^>]+on\w+",
            r"<\s*img[^>]+on\w+",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("输入包含潜在的恶意内容")
        return v


class AgentConfig(BaseModel):
    """Agent configuration validation model"""

    agent_id: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    display_name: str = Field(..., min_length=1, max_length=200)
    expertise_tags: List[str] = Field(default_factory=list, max_length=20)
    style_overrides: Optional[Dict[str, str]] = Field(default_factory=dict)

    @field_validator("expertise_tags")
    @classmethod
    def validate_expertise_tags(cls, v):
        if not v:
            return v
        for tag in v:
            if len(tag) > 50:
                raise ValueError(f"专业标签过长: {tag}")
            if not tag.strip():
                raise ValueError("专业标签不能为空")
        return [tag.strip() for tag in v]

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v):
        if v.startswith("_") or v.endswith("_"):
            raise ValueError("Agent ID不能以下划线开头或结尾")
        return v


class LLMRequest(BaseModel):
    """LLM request validation model"""

    prompt: str = Field(..., min_length=1, max_length=50000)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    max_tokens: int = Field(default=500, ge=1, le=8000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    @field_validator("prompt", "system_prompt")
    @classmethod
    def validate_prompts(cls, v):
        if v is None:
            return v
        v = v.strip()
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
    """Search query validation model"""

    query: str = Field(..., min_length=1, max_length=500)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("搜索查询不能为空")
        if re.search(r"[<>{}]", v):
            raise ValueError("搜索查询包含非法字符")
        return v


class FileUpload(BaseModel):
    """File upload validation model"""

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., pattern=r"^[a-zA-Z0-9]+/[a-zA-Z0-9\-\+\.]+$")
    size_bytes: int = Field(..., ge=1, le=10_000_000)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v):
        v = v.replace("/", "").replace("\\", "").replace("..", "")
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

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v):
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
    try:
        return model_class(**data)
    except ValidationError as e:
        errors = []
        for error in e.errors():
            field = ".".join(str(x) for x in error["loc"])
            message = error["msg"]
            errors.append(f"{field}: {message}")
        raise ValueError(f"输入验证失败: {', '.join(errors)}")


def sanitize_html(text: str) -> str:
    if not text:
        return text
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
    if current_depth > max_depth:
        raise ValueError(f"JSON嵌套深度超过限制: {max_depth}")
    if isinstance(data, dict):
        for value in data.values():
            validate_json_structure(value, max_depth, current_depth + 1)
    elif isinstance(data, list):
        for item in data:
            validate_json_structure(item, max_depth, current_depth + 1)
    return True


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
