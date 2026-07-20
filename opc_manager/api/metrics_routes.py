"""指标 API 路由。

端点:
  POST   /api/v1/metrics/experience   提交体验指标评分
  POST   /api/v1/metrics/nps          提交 NPS 评分
  GET    /api/v1/metrics/summary      查询指标汇总
  POST   /api/v1/metrics/export       上报脱敏数据（需 X-Confirm-Export 头）
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from opc_manager.api import (
    EXPORT_COOLDOWN_SECONDS,
    get_current_user,
)
from opc_manager.api.models import (
    ExperienceMetricRequest,
    ExportRequest,
    ExportResponse,
    MetricResponse,
    MetricsSummary,
    NPSRequest,
)
from opc_manager.metrics_collector import (
    MetricsCollectionError,
    MetricsCollector,
    get_metrics_collector,
)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


def _get_collector(request: Request) -> MetricsCollector:
    """从 app.state 获取 MetricsCollector（测试时由 fixture 注入）。"""
    collector = getattr(request.app.state, "metrics_collector", None)
    if collector is not None:
        return collector
    return get_metrics_collector()


def _ensure_user_scope(user: dict, target_user_id: Optional[str]) -> Optional[str]:
    """普通用户只能操作自己；admin 可指定任意 user_id 或全部。"""
    if user.get("role") == "admin":
        return target_user_id
    if target_user_id is not None and target_user_id != user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="普通用户只能操作自己的数据",
        )
    return user["user_id"]


@router.post(
    "/experience", response_model=MetricResponse, status_code=status.HTTP_201_CREATED
)
async def submit_experience_metric(
    payload: ExperienceMetricRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> MetricResponse:
    """提交体验指标评分（dialogue_naturalness / result_satisfaction / proactive_service）。"""
    _ensure_user_scope(user, payload.user_id)
    collector = _get_collector(request)
    try:
        record_id = collector.record_experience(
            user_id=payload.user_id,
            metric_type=payload.metric_type.value,
            score=payload.score,
            session_id=payload.session_id,
            comment=payload.comment,
            metadata={
                "source": "api_v1",
                "channel": "post_task",
            },
        )
    except MetricsCollectionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"体验指标写入失败: {e}",
        )
    return MetricResponse(id=record_id, status="success", message="ok")


@router.post("/nps", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
async def submit_nps(
    payload: NPSRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> MetricResponse:
    """提交 NPS 评分（0-10 整数）。"""
    _ensure_user_scope(user, payload.user_id)
    collector = _get_collector(request)
    try:
        record_id = collector.record_nps(
            user_id=payload.user_id,
            score=payload.score,
            comment=payload.comment or "",
            metadata={
                "source": "api_v1",
                "channel": payload.channel,
            },
        )
    except MetricsCollectionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"NPS 写入失败: {e}",
        )
    return MetricResponse(id=record_id, status="success", message="ok")


@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    request: Request,
    metric_type: str = Query(
        ..., description="experience/nps/activation/upgrade/flywheel/payment"
    ),
    start_date: str = Query(..., description="ISO 8601 起始日期"),
    end_date: str = Query(..., description="ISO 8601 结束日期"),
    user_id: Optional[str] = Query(None, description="用户 ID（admin 可查全局）"),
    user: dict = Depends(get_current_user),
) -> MetricsSummary:
    """查询指标汇总（总数/均值/中位数/P90）。"""
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date 不能晚于 end_date",
        )
    scoped_user = _ensure_user_scope(user, user_id)
    collector = _get_collector(request)
    try:
        summary = collector.get_metrics_summary(
            metric_type=metric_type,
            start_date=start_date,
            end_date=end_date,
            user_id=scoped_user,
        )
    except MetricsCollectionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    # experience 类型补充 3 个子指标汇总
    sub_metrics = None
    if metric_type == "experience":
        sub_metrics = []
        for sub in (
            "dialogue_naturalness",
            "result_satisfaction",
            "proactive_service",
        ):
            try:
                sub_summary = collector.get_metrics_summary(
                    metric_type=sub,
                    start_date=start_date,
                    end_date=end_date,
                    user_id=scoped_user,
                )
                sub_metrics.append(MetricsSummary(**sub_summary))
            except Exception:  # noqa: BLE001 - 子指标失败不阻塞主响应
                continue
    return MetricsSummary(
        metric_type=summary["metric_type"],
        total_count=summary["total_count"],
        avg_score=summary["avg_score"],
        p50_score=summary["p50_score"],
        p90_score=summary["p90_score"],
        time_range=summary["time_range"],
        sub_metrics=sub_metrics,
    )


@router.post("/export", response_model=ExportResponse)
async def export_metrics(
    payload: ExportRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    x_confirm_export: Optional[str] = Header(None, alias="X-Confirm-Export"),
) -> ExportResponse:
    """上报脱敏指标到专业版网关。

    前置条件:
      - X-Confirm-Export: true 头（UI 二次确认）→ 否则 428
      - 距上次上报不足 1 小时 → 429（force=True 跳过）
    """
    if x_confirm_export != "true":
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="需要 UI 二次确认，请通过设置页弹窗触发并携带 X-Confirm-Export: true 头",
        )
    collector = _get_collector(request)
    # 1 小时冷却检查
    last_export = collector.get_last_export_at()
    if not payload.force and last_export:
        try:
            last_dt = datetime.fromisoformat(last_export)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if elapsed < EXPORT_COOLDOWN_SECONDS:
                retry_after = int(EXPORT_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"上报冷却中，剩余 {retry_after} 秒",
                    headers={"Retry-After": str(retry_after)},
                )
        except HTTPException:
            raise
        except (ValueError, TypeError):
            pass  # 解析失败时放行
    try:
        # 将 metric_types 中的 "nps" 映射为 "experience"（NPS 存于 metrics_experience 表）
        export_types: Optional[List[str]] = None
        if payload.metric_types is not None:
            export_types = []
            for mt in payload.metric_types:
                if mt == "nps":
                    if "experience" not in export_types:
                        export_types.append("experience")
                else:
                    if mt not in export_types:
                        export_types.append(mt)
        exported_list = collector.export_anonymized(
            start_date=payload.start_date.isoformat(),
            end_date=payload.end_date.isoformat(),
            metric_types=export_types,
        )
    except Exception as e:  # noqa: BLE001 - 上报失败返回 502
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"专业版网关上报失败: {e}",
        )
    # 按 metric_category 分组（export_anonymized 返回扁平 list，每行含 metric_category 字段）
    exported: dict = {}
    for row in exported_list:
        cat = row.get("metric_category", "unknown")
        exported.setdefault(cat, []).append(row)
    # 如果请求方只请求 nps，从 experience 分组中过滤出 metric_type=nps 的行
    if (
        payload.metric_types is not None
        and "nps" in payload.metric_types
        and "experience" not in payload.metric_types
    ):
        nps_rows = [
            r for r in exported.get("experience", []) if r.get("metric_type") == "nps"
        ]
        if nps_rows:
            exported["nps"] = nps_rows
        exported.pop("experience", None)
    total_count = sum(len(v) for v in exported.values())
    # 记录导出事件（用于下次冷却检查）
    try:
        collector.set_last_export_at(exported_count=total_count)
    except Exception:  # noqa: BLE001 - 日志写入失败不阻塞响应
        pass
    return ExportResponse(
        success=True,
        exported_count=total_count,
        failed_count=0,
        message=f"已上报 {total_count} 条脱敏记录",
    )
