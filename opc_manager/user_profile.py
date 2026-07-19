import logging
import time
from typing import Dict, List, Any
from collections import Counter

logger = logging.getLogger(__name__)

_data_manager = None


def _get_dm() -> Any:
    global _data_manager
    if _data_manager is None:
        from opc_manager import data_manager

        _data_manager = data_manager
    return _data_manager


class UserProfile:

    _initialized = False

    def __init__(self) -> None:
        if not UserProfile._initialized:
            _get_dm().init_db()
            UserProfile._initialized = True

    def record_interaction(
        self,
        intent_type: str,
        goal: str,
        skill_used: str,
        result_success: bool,
        user_feedback: str = "",
    ) -> None:
        dm = _get_dm()
        interaction_id = dm.gen_id()
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        dm.execute_write(
            "INSERT INTO interaction_log "
            "(id, intent_type, goal, skill_used, success, user_feedback, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                interaction_id,
                intent_type,
                goal,
                skill_used,
                1 if result_success else 0,
                user_feedback,
                now,
            ),
        )

    def get_preferred_skills(self, intent_type: str) -> List[str]:
        rows = _get_dm().execute_query(
            "SELECT skill_used, COUNT(*) as cnt FROM interaction_log "
            "WHERE intent_type=? AND success=1 "
            "GROUP BY skill_used ORDER BY cnt DESC LIMIT 10",
            (intent_type,),
        )
        return [row["skill_used"] for row in rows]

    def get_usage_patterns(self) -> Dict[str, Any]:
        dm = _get_dm()
        total_rows = dm.execute_query("SELECT COUNT(*) as cnt FROM interaction_log")
        total = total_rows[0]["cnt"] if total_rows else 0

        skill_rows = dm.execute_query(
            "SELECT skill_used, COUNT(*) as cnt FROM interaction_log GROUP BY skill_used ORDER BY cnt DESC LIMIT 10"
        )
        top_skills = [
            {"skill": row["skill_used"], "count": row["cnt"]} for row in skill_rows
        ]

        intent_rows = dm.execute_query(
            "SELECT intent_type, COUNT(*) as cnt FROM interaction_log GROUP BY intent_type ORDER BY cnt DESC LIMIT 10"
        )
        top_intents = [
            {"intent": row["intent_type"], "count": row["cnt"]} for row in intent_rows
        ]

        success_rows = dm.execute_query(
            "SELECT success, COUNT(*) as cnt FROM interaction_log GROUP BY success"
        )
        success_rate = 0.0
        success_count = 0
        for row in success_rows:
            if row["success"] == 1:
                success_count = row["cnt"]
        if total > 0:
            success_rate = round(success_count / total, 2)

        time_rows = dm.execute_query(
            "SELECT created_at FROM interaction_log ORDER BY created_at DESC LIMIT 100"
        )
        active_hours = []
        for row in time_rows:
            try:
                hour = int(row["created_at"].split("T")[1].split(":")[0])
                active_hours.append(hour)
            except (IndexError, ValueError, AttributeError):
                pass
        hour_counter = Counter(active_hours)
        peak_hours = [h for h, _ in hour_counter.most_common(5)]

        return {
            "total_interactions": total,
            "top_skills": top_skills,
            "top_intents": top_intents,
            "success_rate": success_rate,
            "peak_hours": peak_hours,
        }

    def get_skill_recommendations(self) -> List[Dict[str, Any]]:
        dm = _get_dm()
        recommendations = []

        failed_rows = dm.execute_query(
            "SELECT intent_type, goal, COUNT(*) as cnt FROM interaction_log "
            "WHERE success=0 GROUP BY intent_type ORDER BY cnt DESC LIMIT 5"
        )
        for row in failed_rows:
            top_skill_rows = dm.execute_query(
                "SELECT skill_used, COUNT(*) as cnt FROM interaction_log "
                "WHERE intent_type=? AND success=1 "
                "GROUP BY skill_used ORDER BY cnt DESC LIMIT 1",
                (row["intent_type"],),
            )
            reason = f"意图 '{row['intent_type']}' 频繁失败({row['cnt']}次)"
            if top_skill_rows:
                reason += f"，可尝试已验证的 '{top_skill_rows[0]['skill_used']}' 技能"
            else:
                reason += "，建议安装相关外部技能"
            recommendations.append(
                {
                    "type": "failed_intent",
                    "intent_type": row["intent_type"],
                    "goal": row["goal"],
                    "fail_count": row["cnt"],
                    "suggestion": reason,
                }
            )

        unknown_rows = dm.execute_query(
            "SELECT goal, COUNT(*) as cnt FROM interaction_log "
            "WHERE intent_type='unknown' GROUP BY goal ORDER BY cnt DESC LIMIT 5"
        )
        for row in unknown_rows:
            recommendations.append(
                {
                    "type": "unknown_intent",
                    "goal": row["goal"],
                    "count": row["cnt"],
                    "suggestion": f"无法识别的意图 '{row['goal']}' 出现 {row['cnt']} 次，建议搜索外部技能",
                }
            )

        return recommendations

    def record_preference(self, key: str, value: str) -> None:
        _get_dm().set_preference(key, value)

    def get_preference(self, key: str, default: str = "") -> str:
        return _get_dm().get_preference(key, default)

    def get_decision_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = _get_dm().execute_query(
            "SELECT * FROM interaction_log ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [
            {
                "id": row["id"],
                "intent_type": row["intent_type"],
                "goal": row["goal"],
                "skill_used": row["skill_used"],
                "success": bool(row["success"]),
                "user_feedback": row.get("user_feedback", ""),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def update_interaction(self, interaction_id: str, **kwargs: Any) -> bool:
        dm = _get_dm()
        rows = dm.execute_query(
            "SELECT id FROM interaction_log WHERE id=?", (interaction_id,)
        )
        if not rows:
            return False
        allowed = {"intent_type", "goal", "skill_used", "success", "user_feedback"}
        updates = []
        params = []
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key}=?")
                params.append(value)
        if not updates:
            return False
        params.append(interaction_id)
        dm.execute_write(
            f"UPDATE interaction_log SET {', '.join(updates)} WHERE id=?",  # nosec B608 — column names from `allowed` whitelist, values parameterized
            tuple(params),
        )
        return True
