"""Pydantic v2 模型 — 用户反馈与指标 API。

参考 API_DESIGN_feedback_and_metrics.md §4 与 validators.py 的写法。
所有 comment 字段经过 prompt injection / XSS 防护。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

import re
from pydantic import BaseModel, Field, field_validator, model_validator

from opc_manager.validators import sanitize_html


class FeedbackCategory(str, Enum):
    """反馈类别枚举"""

    BUG = "bug"
    SUGGESTION = "suggestion"
    PRAISE = "praise"
    QUESTION = "question"


class ExperienceMetricType(str, Enum):
    """体验指标类型枚举"""

    DIALOGUE_NATURALNESS = "dialogue_naturalness"
    RESULT_SATISFACTION = "result_satisfaction"
    PROACTIVE_SERVICE = "proactive_service"


class MetricType(str, Enum):
    """指标类型枚举（含 NPS）"""

    DIALOGUE_NATURALNESS = "dialogue_naturalness"
    RESULT_SATISFACTION = "result_satisfaction"
    PROACTIVE_SERVICE = "proactive_service"
    NPS = "nps"


# 共用危险模式：XSS + prompt injection（与 validators.py 第 28-46 行对齐）
_DANGEROUS_PATTERNS = [
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
    r"ignore\s+(previous|above)\s+instructions",
    r"disregard\s+(previous|above)\s+instructions",
    r"system\s*prompt",
]


def _sanitize_text(v: str) -> str:
    """共用：危险模式过滤 + HTML 转义。命中危险模式抛 ValueError 触发 422。"""
    if not v:
        return v
    v = v.strip()
    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, v, re.IGNORECASE):
            raise ValueError("输入包含潜在恶意内容")
    return sanitize_html(v)


def _sanitize_optional_text(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    return _sanitize_text(v)


class FeedbackRequest(BaseModel):
    """用户反馈请求体"""

    user_id: str = Field(..., min_length=1, max_length=100, description="用户 ID")
    rating: int = Field(..., ge=1, le=5, description="1-5 星评分")
    comment: str = Field("", max_length=2000, description="文字反馈")
    category: FeedbackCategory = Field(..., description="反馈类别")
    skill_id: Optional[str] = Field(None, max_length=100, description="关联技能 ID")
    session_id: Optional[str] = Field(None, max_length=100, description="关联会话 ID")
    timestamp: datetime = Field(..., description="反馈发生时间，ISO 8601")

    @field_validator("comment")
    @classmethod
    def sanitize_comment(cls, v: str) -> str:
        return _sanitize_text(v)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp 必须包含时区信息")
        now = datetime.now(timezone.utc)
        delta = now - v
        if delta.days > 7:
            raise ValueError("timestamp 不能早于当前时间 7 天以上")
        if delta.total_seconds() < -300:
            raise ValueError("timestamp 不能晚于当前时间 5 分钟以上")
        return v


class FeedbackResponse(BaseModel):
    """用户反馈响应体"""

    id: str = Field(..., description="反馈记录 ID，UUID v4")
    user_id: str = Field(..., description="用户 ID")
    rating: int = Field(..., ge=1, le=5, description="1-5 星评分")
    comment: Optional[str] = Field("", description="文字反馈（已脱敏存储）")
    category: FeedbackCategory = Field(..., description="反馈类别")
    skill_id: Optional[str] = Field(None, description="关联技能 ID")
    session_id: Optional[str] = Field(None, description="关联会话 ID")
    timestamp: datetime = Field(..., description="反馈发生时间")
    created_at: datetime = Field(..., description="记录写入数据库时间")

    model_config = {"use_enum_values": True}


class BatchFeedbackError(BaseModel):
    """批量反馈中的单条错误"""

    index: int = Field(..., description="失败条目在请求列表中的下标")
    error: str = Field(..., description="错误原因")


class BatchFeedbackResponse(BaseModel):
    """批量反馈响应体"""

    success_count: int = Field(..., ge=0, description="成功写入条数")
    failed_count: int = Field(..., ge=0, description="失败条数")
    errors: List[BatchFeedbackError] = Field(
        default_factory=list, description="失败详情列表"
    )


class ExperienceMetricRequest(BaseModel):
    """体验指标评分请求体"""

    user_id: str = Field(..., min_length=1, max_length=100)
    metric_type: ExperienceMetricType = Field(..., description="体验指标类型")
    score: float = Field(..., ge=1.0, le=5.0, description="1.0-5.0 评分，支持半星")
    session_id: Optional[str] = Field(None, max_length=100, description="关联会话 ID")
    comment: Optional[str] = Field(None, max_length=500, description="可选评语")
    timestamp: datetime = Field(..., description="评分发生时间")

    @field_validator("comment")
    @classmethod
    def sanitize_comment(cls, v: Optional[str]) -> Optional[str]:
        return _sanitize_optional_text(v)

    @field_validator("score")
    @classmethod
    def round_score(cls, v: float) -> float:
        # 仅保留 0.5 精度，避免前端传 4.7 这样的非标准分
        return round(v * 2) / 2


class NPSRequest(BaseModel):
    """NPS 评分请求体"""

    user_id: str = Field(..., min_length=1, max_length=100)
    score: int = Field(..., ge=0, le=10, description="0-10 整数评分")
    comment: Optional[str] = Field(None, max_length=1000, description="可选评语")
    timestamp: datetime = Field(..., description="评分发生时间")
    channel: str = Field("post_task", pattern=r"^(post_task|weekly_survey)$")

    @field_validator("comment")
    @classmethod
    def sanitize_comment(cls, v: Optional[str]) -> Optional[str]:
        return _sanitize_optional_text(v)


class MetricResponse(BaseModel):
    """指标写入通用响应体"""

    id: str = Field(..., description="指标记录 ID，UUID v4")
    status: str = Field(..., pattern=r"^(success|pending|failed)$", description="写入状态")
    message: str = Field("", description="附加信息（如失败原因）")


class MetricsSummary(BaseModel):
    """指标汇总响应体"""

    metric_type: str = Field(..., description="指标类型")
    total_count: int = Field(..., ge=0, description="总样本数")
    avg_score: float = Field(..., description="平均分")
    p50_score: float = Field(..., description="中位数")
    p90_score: float = Field(..., description="90 分位")
    time_range: str = Field(..., description="时间范围，格式 start_date~end_date")
    sub_metrics: Optional[List["MetricsSummary"]] = Field(
        None, description="子指标汇总（仅 experience 类型）"
    )


class ExportRequest(BaseModel):
    """脱敏数据上报请求体"""

    metric_types: Optional[List[str]] = Field(
        None,
        description="要上报的指标类型列表，None 表示全部。可选："
        "activation/upgrade/flywheel/payment/nps/experience",
    )
    start_date: datetime = Field(..., description="起始时间")
    end_date: datetime = Field(..., description="结束时间")
    force: bool = Field(False, description="是否跳过 1 小时冷却")

    @field_validator("metric_types")
    @classmethod
    def validate_metric_types(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        allowed = {"activation", "upgrade", "flywheel", "payment", "nps", "experience"}
        for mt in v:
            if mt not in allowed:
                raise ValueError(f"不支持的 metric_type: {mt}")
        return v

    @model_validator(mode="after")
    def validate_date_range(self) -> "ExportRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date 不能早于 start_date")
        return self


class ExportResponse(BaseModel):
    """脱敏数据上报响应体"""

    success: bool = Field(..., description="整体上报是否成功")
    exported_count: int = Field(..., ge=0, description="成功上报条数")
    failed_count: int = Field(..., ge=0, description="失败条数")
    message: str = Field("", description="附加信息（如网关返回的提示）")


MetricsSummary.model_rebuild()
