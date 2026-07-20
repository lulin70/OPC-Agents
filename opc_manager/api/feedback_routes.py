"""用户反馈 API 路由。

端点:
  POST   /api/v1/feedback         提交单条反馈（JWT/X-API-Key）
  POST   /api/v1/feedback/batch   批量提交反馈（admin 专属）
  GET    /api/v1/feedback         查询反馈历史（仅本人，admin 全部）

依赖:
  - opc_manager.metrics_collector.MetricsCollector (生产真实类)
  - opc_manager.api 共享的认证/限流依赖
"""

from datetime import datetime, timezone
from typing import List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from opc_manager.api import (
    BATCH_RATE_LIMIT_PER_MIN,
    get_current_user,
    rate_limit_check,
    require_admin,
)
from opc_manager.api.models import (
    BatchFeedbackError,
    BatchFeedbackResponse,
    FeedbackCategory,
    FeedbackRequest,
    FeedbackResponse,
)
from opc_manager.metrics_collector import (
    MetricsCollectionError,
    MetricsCollector,
    get_metrics_collector,
)

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

_BATCH_MAX_ITEMS = 500


def _get_collector(request: Request) -> MetricsCollector:
    """从 app.state 获取 MetricsCollector（测试时由 fixture 注入）。"""
    collector = getattr(request.app.state, "metrics_collector", None)
    if collector is not None:
        return collector
    return get_metrics_collector()


def _to_response(row: dict) -> FeedbackResponse:
    """将数据库行映射为 FeedbackResponse。"""
    return FeedbackResponse(
        id=row["record_id"],
        user_id=row["user_id"],
        rating=int(row["rating"]),
        comment=row.get("comment") or "",
        category=FeedbackCategory(row.get("category") or FeedbackCategory.PRAISE.value),
        skill_id=row.get("skill_id"),
        session_id=row.get("session_id"),
        timestamp=cast(datetime, row.get("timestamp") or row.get("created_at")),
        created_at=cast(datetime, row.get("created_at")),
    )


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> FeedbackResponse:
    """提交单条用户反馈。

    业务规则:
      - 普通用户只能提交自己 user_id 的反馈；admin 可提交任意
      - comment 已在 Pydantic 层过滤 prompt injection / XSS
      - timestamp 不能早于 7 天前
    """
    # 权限校验：普通用户跨用户提交 → 403
    if user.get("role") != "admin" and payload.user_id != user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="普通用户只能提交自己的反馈",
        )
    collector = _get_collector(request)
    try:
        record_id = collector.record_feedback(
            user_id=payload.user_id,
            rating=payload.rating,
            comment=payload.comment or "",
            category=payload.category.value,
            skill_id=payload.skill_id,
            session_id=payload.session_id,
            timestamp=payload.timestamp.isoformat(),
            metadata={"source": "api_v1", "client_role": user.get("role")},
        )
    except MetricsCollectionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"反馈写入失败: {e}",
        )
    rows = collector.get_feedback_list(user_id=payload.user_id, limit=1, offset=0)
    row = (
        rows[0]
        if rows
        else {
            "record_id": record_id,
            "user_id": payload.user_id,
            "rating": payload.rating,
            "comment": payload.comment or "",
            "category": payload.category.value,
            "skill_id": payload.skill_id,
            "session_id": payload.session_id,
            "timestamp": payload.timestamp.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return _to_response(row)


@router.post("/batch", response_model=BatchFeedbackResponse)
async def submit_batch_feedback(
    payload: List[FeedbackRequest],
    request: Request,
    user: dict = Depends(require_admin),
) -> BatchFeedbackResponse:
    """批量提交反馈（admin 专属，单次最多 500 条）。

    单条验证失败不影响其他条目；失败项记入 errors 数组。
    """
    if len(payload) > _BATCH_MAX_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"批量提交最多 {_BATCH_MAX_ITEMS} 条，收到 {len(payload)} 条",
        )
    # 批量端点单独限流：5 req/min
    rate_limit_check(request, BATCH_RATE_LIMIT_PER_MIN)

    collector = _get_collector(request)
    success_count = 0
    errors: List[BatchFeedbackError] = []
    for idx, item in enumerate(payload):
        try:
            collector.record_feedback(
                user_id=item.user_id,
                rating=item.rating,
                comment=item.comment or "",
                category=item.category.value,
                skill_id=item.skill_id,
                session_id=item.session_id,
                timestamp=item.timestamp.isoformat(),
                metadata={"source": "api_v1_batch", "batch_index": idx},
            )
            success_count += 1
        except MetricsCollectionError as e:
            errors.append(BatchFeedbackError(index=idx, error=str(e)))
        except Exception as e:  # noqa: BLE001 - 批量场景需隔离单条异常
            errors.append(BatchFeedbackError(index=idx, error=f"unexpected: {e}"))
    return BatchFeedbackResponse(
        success_count=success_count,
        failed_count=len(errors),
        errors=errors,
    )


@router.get("", response_model=List[FeedbackResponse])
async def list_feedback(
    request: Request,
    user_id: Optional[str] = Query(None, description="用户 ID（admin 可查任意）"),
    start_date: Optional[str] = Query(None, description="ISO 8601 起始日期"),
    end_date: Optional[str] = Query(None, description="ISO 8601 结束日期"),
    category: Optional[str] = Query(None, description="bug/suggestion/praise/question"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
) -> List[FeedbackResponse]:
    """查询反馈历史。

    权限:
      - 普通用户：仅自己 user_id，传其他值 → 403
      - admin：可查任意 user_id 或全部
    业务规则: start_date > end_date → 400；按 created_at DESC 排序。
    """
    if user.get("role") != "admin":
        if user_id is not None and user_id != user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="普通用户只能查询自己的反馈",
            )
        user_id = user["user_id"]
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date 不能晚于 end_date",
        )
    if category and category not in {"bug", "suggestion", "praise", "question"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法 category: {category}",
        )
    collector = _get_collector(request)
    rows = collector.get_feedback_list(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        category=category,
        limit=limit,
        offset=offset,
    )
    return [_to_response(r) for r in rows]
