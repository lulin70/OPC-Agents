import re
import logging
from typing import Dict, List, Optional, Tuple
from opc_manager.task_types import TaskType

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Regex-based intent classifier — Maps user input to one of 5 task types

    Design intent (why not use LLM?):
    1. **Zero latency**: Regex match <1ms vs LLM call >500ms
    2. **Zero cost**: No API call fees
    3. **Deterministic**: Same input always gets same result, easy to debug
    4. **Offline available**: No dependency on external services
    5. **Accurate enough**: For current 5 coarse-grained categories, regex coverage >95%

    Classification priority (PATTERNS dict order is the priority):
    INFO_COLLECTION > CONTENT_GENERATION > DATA_ANALYSIS
    > SCENARIO_BASED > GENERAL_CHAT(fallback)

    Extension method:
    Adding new task types only requires adding key-value pairs + regex list in PATTERNS.
    Note: Keep priority order from high to low.
    """

    FOLLOW_UP_PATTERNS = [
        r"补充",
        r"加上",
        r"添加",
        r"增加",
        r"修改",
        r"调整",
        r"缩短",
        r"延长",
        r"删掉",
        r"去掉",
        r"替换",
        r"换成",
        r"展开",
        r"详细.*说明",
        r"更具体",
        r"细化",
        r"完善",
        r"优化",
        r"改进",
        r"能不能.*改",
        r"能不能.*加",
        r"能不能.*缩短",
        r"能不能.*延长",
        r"把.*改成",
        r"把.*换成",
        r"add",
        r"include",
        r"modify",
        r"change",
        r"adjust",
        r"expand",
        r"elaborate",
        r"detail",
        r"refine",
        r"improve",
        r"update",
        r"replace",
        r"追加",
        r"もう少し",
        r"追加して",
        r"修正して",
        r"変更して",
        r"詳細に",
    ]

    NEW_TASK_PATTERNS = [
        r"帮我写",
        r"帮我生成",
        r"帮我创建",
        r"帮我做",
        r"帮我制定",
        r"帮我规划",
        r"write.*(?:report|plan|proposal|document)",
        r"create.*(?:new|fresh|document)",
        r"generate",
        r"新.*(?:方案|计划|报告)",
    ]

    PATTERNS = {
        TaskType.INFO_COLLECTION: [
            r"收集",
            r"搜索",
            r"查找",
            r"了解.*趋势",
            r".*动向",
            r"调研",
            r"最新.*消息",
            r".*政策",
            r"行业.*动态",
            r"竞品.*分析",
            r".*资讯",
            r"落地.*政策",
            r"collect",
            r"search",
            r"find",
            r"research",
            r"latest.*trends?",
            r"industry.*news",
            r"competitor.*analysis",
            r"gather",
            r"look up",
            r"収集",
            r"検索",
            r"調べ",
            r"最新.*トレンド",
            r"業界.*動向",
            r"競合.*分析",
        ],
        TaskType.CONTENT_GENERATION: [
            r"写|撰写|起草|生成.*(报告|方案|文章|文案|计划|总结)",
            r"帮我.*(写|做|制作)",
            r"(报告|方案|文章|文案).*(怎么写|如何写)",
            r"write|draft|create|generate",
            r"help me (write|create|make|draft)",
            r"compose",
            r"put together",
            r"書いて|作成",
            r"(レポート|企画書|記事).*(書き方|作り方)",
        ],
        TaskType.DATA_ANALYSIS: [
            r"分析|评估|对比|比较|判断|预测",
            r".*怎么样",
            r".*好不好",
            r"是否应该",
            r"analyz|evaluat|compar|assess|predict",
            r"should i",
            r"is it (worth|good|better)",
            r"評価|比較|予測",
            r"どう.*か",
            r"べきか",
        ],
        TaskType.SCENARIO_BASED: [
            r"执行.*场景",
            r"帮我执行",
            r"运行.*场景",
            r"内容日历",
            r"数字产品发布",
            r"用户反馈分析",
            r"咨询提案",
            r"电商运营优化",
            r"项目交付物",
            r"新产品发布",
            r"会议组织",
            r"报告撰写",
            r"run.*scenario",
            r"execute.*scenario",
            r"content calendar",
            r"product launch",
            r"user feedback",
            r"consulting proposal",
            r"ecommerce optimization",
            r"meeting organization",
            r"シナリオ.*実行",
            r"コンテンツカレンダー",
            r"製品ローンチ",
            r"ユーザーフィードバック",
            r"コンサルティング提案",
        ],
    }

    _COMPILED_PATTERNS: Dict[TaskType, list] = {}
    _COMPILED_FOLLOW_UP: list = []
    _COMPILED_NEW_TASK: list = []

    @classmethod
    def _ensure_compiled(cls):
        if not cls._COMPILED_PATTERNS:
            cls._COMPILED_PATTERNS = {
                task_type: [re.compile(p, re.IGNORECASE) for p in patterns]
                for task_type, patterns in cls.PATTERNS.items()
            }
            cls._COMPILED_FOLLOW_UP = [
                re.compile(p, re.IGNORECASE) for p in cls.FOLLOW_UP_PATTERNS
            ]
            cls._COMPILED_NEW_TASK = [
                re.compile(p, re.IGNORECASE) for p in cls.NEW_TASK_PATTERNS
            ]

    @classmethod
    def classify(cls, user_input: str) -> Tuple[TaskType, float]:
        cls._ensure_compiled()
        text = user_input.lower().strip()
        for task_type, compiled_list in cls._COMPILED_PATTERNS.items():
            for compiled in compiled_list:
                if compiled.search(text):
                    return task_type, 0.85
        return TaskType.GENERAL_CHAT, 0.5

    @classmethod
    def is_follow_up(cls, user_input: str) -> bool:
        """Detect if user input is a follow-up request (supplement/modify/adjust)

        A follow-up is when the user wants to modify or supplement previous output,
        not start a completely new task. This is critical for multi-turn conversation:
        - Follow-up: "补充竞品分析" → Should reference previous output and modify it
        - New task: "帮我写Q2方案" → Should start fresh

        Detection logic:
        1. NEW_TASK_PATTERNS have priority — if matched, it's NOT a follow-up
        2. Then check FOLLOW_UP_PATTERNS (supplement/modify/adjust keywords)
        3. Always returns False if no conversation history exists (caller's responsibility)

        Args:
            user_input: User's original input text

        Returns:
            True if this appears to be a follow-up request, False otherwise
        """
        text = user_input.strip()
        cls._ensure_compiled()
        for compiled in cls._COMPILED_NEW_TASK:
            if compiled.search(text):
                return False
        for compiled in cls._COMPILED_FOLLOW_UP:
            if compiled.search(text):
                return True
        return False
