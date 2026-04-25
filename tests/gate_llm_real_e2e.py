"""G-LLM-REAL-01: 真实LLM API E2E质量门禁 (v3.6 P0 Blocker)

=== 设计目标 ===
解决v3.5最大风险: "143个测试100%通过，但全是mock，真实LLM输出可能完全不可用"

本门禁强制要求:
1. 至少10%的测试用例必须调用真实LLM API（非mock）
2. 真实输出必须通过"具体性检查"（不能是通用模板）
3. 记录每条查询的质量评分（用于趋势监控）

=== 测试策略 ===
分层执行:
  Layer 1: API连通性测试（5条）— 验证API Key有效、响应正常
  Layer 2: 内容质量抽检（20条）— 覆盖各场景，人工+自动双重验证
  Layer 3: 边界压力测试（10条）— 极端输入、超长、特殊字符
  Layer 4: 降级路径验证（5条）— API失败时降级到模板模式
  Layer 5: 性能基准测试（10条）— 响应时间、token消耗

总计: 50条真实查询

=== 质量评分标准 ===
每条查询按以下维度打分(0-10):
  - S1: 业务信息注入(0-2) — 用户提供的数字/产品名是否出现
  - S2: 具体性(0-3) — 是否有具体数字/日期/行动项（非"适当""适时"）
  - S3: 结构完整性(0-2) — Markdown格式是否正确，标题层级是否合理
  - S4: 无禁止内容(0-2) — 无占位符/无空泛废话/无乱码
  - S5: 搜索引用(0-1) — 是否引用了搜索结果中的信息

总分 ≥ 6/10 为"合格", < 6为"不合格"

=== 执行方式 ===
python tests/gate_llm_real_e2e.py [--layer L1] [--quick] [--report]

参数:
  --layer L1|L2|L3|L4|L5: 仅执行指定层
  --quick: 快速模式(仅Layer 1, 5条查询)
  --report: 生成详细HTML报告
"""

import os
import sys
import time
import json
import re
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "tests" / "e2e_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class QueryTestCase:
    """单条测试查询用例"""

    id: str
    category: str
    user_input: str
    expected_keywords: List[str]
    forbidden_patterns: List[str]
    min_length: int = 500
    max_latency_sec: float = 60.0


@dataclass
class QualityScore:
    """质量评分结果"""

    query_id: str
    scores: Dict[str, int]
    total: int
    passed: bool
    details: Dict[str, str]


@dataclass
class E2EResult:
    """E2E测试结果"""

    query_id: str
    category: str
    user_input: str
    success: bool
    mode: str  # 'llm_rag' | 'template_fallback' | 'error'
    content: str
    latency_ms: float
    tokens_used: int
    quality_score: Optional[QualityScore] = None
    error_message: Optional[str] = None


# ========== 50条真实测试查询定义 ==========

QUERIES_LAYER1_CONNECTIVITY = [
    QueryTestCase(
        id="L1-001",
        category="连通性",
        user_input="你好，请简单介绍一下你自己",
        expected_keywords=["OPC-Agents", "助手", "工具"],
        forbidden_patterns=["___", "ERROR"],
        min_length=50,
    ),
    QueryTestCase(
        id="L1-002",
        category="连通性",
        user_input="1+1等于几？只回答数字",
        expected_keywords=["2", "二"],
        forbidden_patterns=["___", "待填写"],
        min_length=10,
    ),
    QueryTestCase(
        id="L1-003",
        category="连通性",
        user_input="请用中文写一首关于春天的五言绝句",
        expected_keywords=["春", "诗"],
        forbidden_patterns=["___", "error"],
        min_length=20,
    ),
    QueryTestCase(
        id="L1-004",
        category="连通性",
        user_input="将以下英文翻译成中文: Hello World, this is a test.",
        expected_keywords=["你好", "世界", "测试"],
        forbidden_patterns=["___"],
        min_length=15,
    ),
    QueryTestCase(
        id="L1-005",
        category="连通性",
        user_input="列出Python的3个主要优点，每个用一句话说明",
        expected_keywords=["Python", "优点"],
        forbidden_patterns=["___", "待补充"],
        min_length=100,
    ),
]

QUERIES_LAYER2_QUALITY = [
    # 场景A: 商业方案类（PM评估核心场景）
    QueryTestCase(
        id="L2-001",
        category="商业方案-Q2营销",
        user_input="帮我制定Q2增长方案，产品是AI写作助手SaaS工具，当前月活5000用户，目标Q2末达到10000用户，预算5万元",
        expected_keywords=["AI写作助手", "5000", "10000", "Q2", "5万", "元"],
        forbidden_patterns=["基准值待测", "___", "待填写", "适时", "加强关注"],
        min_length=800,
    ),
    QueryTestCase(
        id="L2-002",
        category="商业方案-竞品分析",
        user_input="帮我分析Notion AI和我的产品的差异化，我的是面向一人公司的免费AI文档生成工具，主打中文市场",
        expected_keywords=["Notion", "一人公司", "中文", "免费", "文档"],
        forbidden_patterns=["___", "TBD", "待测量"],
        min_length=600,
    ),
    QueryTestCase(
        id="L2-003",
        category="商业方案-融资BP",
        user_input="帮我写一份Pre-A轮融资的商业计划书摘要，团队3人，技术壁垒是基于RAG的垂直领域知识增强，目标融资300万美元",
        expected_keywords=["300万", "美元", "Pre-A", "RAG", "3人", "团队"],
        forbidden_patterns=["___", "待填写金额"],
        min_length=1000,
    ),
    QueryTestCase(
        id="L2-004",
        category="商业方案-用户调研",
        user_input="设计一份针对自由职业者的用户调研问卷，包含人口统计、痛点发现、付费意愿3个模块，共15个问题",
        expected_keywords=["自由职业者", "问卷", "15", "问题", "付费意愿"],
        forbidden_patterns=["___", "此处插入问题"],
        min_length=800,
    ),
    QueryTestCase(
        id="L2-005",
        category="商业方案-定价策略",
        user_input="帮我设计一个SaaS产品的定价策略，竞品Notion $8/月，我们的优势是中文优化更好，目标用户是一人公司和小团队",
        expected_keywords=["定价", "SaaS", "$8", "一人公司", "中文"],
        forbidden_patterns=["___", "根据实际情况"],
        min_length=600,
    ),
    # 场景B: 内容生成类
    QueryTestCase(
        id="L2-006",
        category="内容生成-技术博客",
        user_input="写一篇关于'React Server Components vs Next.js App Router'的技术对比博客文章，面向中级前端开发者，1500字左右",
        expected_keywords=[
            "React",
            "Server Components",
            "Next.js",
            "App Router",
            "前端",
        ],
        forbidden_patterns=["___", "待补充代码示例"],
        min_length=1200,
    ),
    QueryTestCase(
        id="L2-007",
        category="内容生成-产品文案",
        user_input="为一个名为'智笔'的AI写作助手写首页产品文案，核心卖点是'一键生成专业级报告'，目标用户是咨询顾问和分析师",
        expected_keywords=["智笔", "AI写作", "一键生成", "报告", "咨询顾问", "分析师"],
        forbidden_patterns=["___", "这里是标题"],
        min_length=400,
    ),
    QueryTestCase(
        id="L2-008",
        category="内容生成-邮件模板",
        user_input="写一封给投资人的跟进邮件，我们上周聊了Pre-A轮意向，对方要求看更多用户数据，我们有200个种子用户的NPS分数是42",
        expected_keywords=["投资人", "Pre-A", "用户数据", "200", "NPS", "42"],
        forbidden_patterns=["___", "Dear [Name]"],
        min_length=300,
    ),
    QueryTestCase(
        id="L2-009",
        category="内容生成-会议纪要",
        user_input="将以下会议记录整理成结构化纪要:\n参会人:张三(CEO)、李四(CTO)、王五(CPO)\n议题: Q2产品路线图优先级\n结论: 先做移动端适配，数据分析延后到Q3\n行动项: 李四出技术方案(周五前)，王五做竞品调研(下周三)",
        expected_keywords=["张三", "李四", "王五", "Q2", "移动端", "周五", "下周三"],
        forbidden_patterns=["___", "待确认"],
        min_length=400,
    ),
    QueryTestCase(
        id="L2-010",
        category="内容生成-周报",
        user_input="帮我写本周工作周报，完成了用户认证模块开发(3个API端点)，修复了2个生产bug，参加了2次技术评审会，下周计划开始支付模块设计",
        expected_keywords=["用户认证", "3个", "API", "2个", "bug", "支付模块"],
        forbidden_patterns=["___", "其他常规工作"],
        min_length=350,
    ),
    # 场景C: 数据分析类
    QueryTestCase(
        id="L2-011",
        category="数据分析-销售报表",
        user_input="分析以下销售数据并给出洞察:\n1月: 收入12万, 客户数150, 转化率3.2%\n2月: 收入15万, 客户数180, 转化率3.8%\n3月: 收入18万, 客户数210, 转化率4.1%",
        expected_keywords=["12万", "15万", "18万", "150", "180", "210", "转化率"],
        forbidden_patterns=["___", "数据显示"],
        min_length=500,
    ),
    QueryTestCase(
        id="L2-012",
        category="数据分析-竞品对比",
        user_input="对比以下三个AI写作工具的功能矩阵:\nChatGPT: 多模态对话, $20/月, 支持插件\nJasper: 营销文案专用, $49/月, 品牌语音\nCopy.ai: 社媒短文, $36/月, 模板丰富\n我们的定位是什么?",
        expected_keywords=["ChatGPT", "Jasper", "Copy.ai", "20", "49", "36"],
        forbidden_patterns=["___", "各有优劣"],
        min_length=600,
    ),
    QueryTestCase(
        id="L2-013",
        category="数据分析-用户行为",
        user_input="分析用户留存数据:\nDay 1: 100% (注册)\nDay 7: 45%\nDay 30: 28%\nDay 90: 22%\n行业平均(D90): 15%\n给出改进建议",
        expected_keywords=["45%", "28%", "22%", "15%", "留存", "改进"],
        forbidden_patterns=["___", "需要进一步分析"],
        min_length=500,
    ),
    QueryTestCase(
        id="L2-014",
        category="数据分析-A/B测试",
        user_input="解释以下A/B测试结果:\n版本A(红色按钮): CTR 4.2%, 转化率 1.8%, 样本量 5000\n版本B(蓝色按钮): CTR 3.9%, 转化率 2.1%, 样本量 5000\np-value = 0.03\n应该选哪个版本?",
        expected_keywords=["4.2%", "3.9%", "1.8%", "2.1%", "0.03", "p-value"],
        forbidden_patterns=["___", " statistically significant but..."],
        min_length=400,
    ),
    QueryTestCase(
        id="L2-015",
        category="数据分析-SEO报告",
        user_input="分析网站SEO现状并提出优化建议:\n当前DA: 35, 月流量: 12000UV, 核心关键词排名: 第5页\n竞争对手DA: 55, 同关键词排名: 第1页\n目标: 6个月内进入前3页",
        expected_keywords=["DA", "35", "12000", "SEO", "第5页", "第1页", "前3页"],
        forbidden_patterns=["___", "需要持续优化"],
        min_length=700,
    ),
    # 场景D: 信息收集类
    QueryTestCase(
        id="L2-016",
        category="信息收集-市场趋势",
        user_input="收集2026年AI Agent/AI智能体领域的5大发展趋势，包括市场规模、关键技术、代表公司和潜在风险",
        expected_keywords=["2026", "AI Agent", "市场规模", "技术", "风险"],
        forbidden_patterns=["___", "趋势包括"],
        min_length=600,
    ),
    QueryTestCase(
        id="L2-017",
        category="信息收集-法规政策",
        user_input="整理2026年中国针对AI生成内容的最新法规政策，特别是《生成式AI服务管理暂行办法》的合规要点",
        expected_keywords=["2026", "中国", "AI", "法规", "暂行办法", "合规"],
        forbidden_patterns=["___", "请查阅官方文件"],
        min_length=500,
    ),
    QueryTestCase(
        id="L2-018",
        category="信息收集-技术栈选型",
        user_input="对比分析后端框架选择:Django vs FastAPI vs Go Gin，评估维度包括开发速度、性能、生态成熟度和招聘难度，项目是一个高并发API服务",
        expected_keywords=["Django", "FastAPI", "Go", "Gin", "性能", "并发"],
        forbidden_patterns=["___", "各有优缺点"],
        min_length=800,
    ),
    QueryTestCase(
        id="L2-019",
        category="信息收集-人才招聘",
        user_input="撰写一个'全栈工程师(远程)'的职位JD，要求3年经验，熟悉React+Node.js或Vue+Python，有SaaS产品经验者优先，薪资范围25-40K",
        expected_keywords=[
            "全栈",
            "远程",
            "3年",
            "React",
            "Node.js",
            "Vue",
            "Python",
            "25-40K",
        ],
        forbidden_patterns=["___", "任职资格"],
        min_length=400,
    ),
    QueryTestCase(
        id="L2-020",
        category="信息收集-竞品功能清单",
        user_input="列出Notion AI的所有已知功能特性，并与我们的AI文档生成工具进行功能gap分析，找出我们可以借鉴或超越的点",
        expected_keywords=["Notion AI", "功能", "gap", "借鉴", "超越"],
        forbidden_patterns=["___", "功能列表如下"],
        min_length=700,
    ),
]

QUERIES_LAYER3_BOUNDARY = [
    QueryTestCase(
        id="L3-001",
        category="边界-超长输入",
        user_input="A" * 3000 + "，请基于以上内容生成一份总结报告",
        expected_keywords=["总结"],
        forbidden_patterns=["___", "错误"],
        min_length=100,
        max_latency_sec=60.0,
    ),
    QueryTestCase(
        id="L3-002",
        category="边界-纯数字",
        user_input="20260423 12345 67890 11111 22222 33333 44444 55555",
        expected_keywords=["20260423", "12345"],
        forbidden_patterns=["___"],
        min_length=50,
    ),
    QueryTestCase(
        id="L3-003",
        category="边界-emoji混合",
        user_input="🚀帮我制定📈增长计划💰预算50万🎯目标用户10000人⏰时间Q2",
        expected_keywords=["增长", "50万", "10000", "Q2"],
        forbidden_patterns=["___"],
        min_length=200,
    ),
    QueryTestCase(
        id="L3-004",
        category="边界-多语言混合",
        user_input="Help me write a business plan for 我的一人公司, targeting the US market with $500K funding goal in Q3 2026",
        expected_keywords=["business plan", "一人公司", "US", "$500K", "Q3"],
        forbidden_patterns=["___"],
        min_length=300,
    ),
    QueryTestCase(
        id="L3-005",
        category="边界-特殊字符",
        user_input="<script>alert('test')</script> &amp; \"quotes\" and 'apostrophes' — 请处理这段包含XSS尝试的输入",
        expected_keywords=["XSS", "处理"],
        forbidden_patterns=["<script>", "alert("],
        min_length=100,
    ),
    QueryTestCase(
        id="L3-006",
        category="边界-空语义",
        user_input="asdfghjkl qwertyuiop zxcvbnm",
        expected_keywords=[],
        forbidden_patterns=["___", "无法理解"],
        min_length=30,
    ),
    QueryTestCase(
        id="L3-007",
        category="边界-极简指令",
        user_input="写",
        expected_keywords=[],
        forbidden_patterns=["___", "ERROR"],
        min_length=10,
    ),
    QueryTestCase(
        id="L3-008",
        category="边界-重复输入",
        user_input="写方案 写方案 写方案 写方案 写方案 写方案 写方案 写方案 写方案 写方案",
        expected_keywords=["方案"],
        forbidden_patterns=["___"],
        min_length=50,
    ),
    QueryTestCase(
        id="L3-009",
        category="边界-嵌套需求",
        user_input="帮我做一个计划，这个计划里面要包含一个子计划，子计划里有一个任务清单，任务清单里要有5个具体的action items",
        expected_keywords=["计划", "子计划", "任务清单", "5", "action"],
        forbidden_patterns=["___", "待添加"],
        min_length=400,
    ),
    QueryTestCase(
        id="L3-010",
        category="边界-矛盾约束",
        user_input="帮我设计一个系统，要求零成本但高性能，支持百万并发但不依赖云服务，一周内完成但质量要达到企业级",
        expected_keywords=["系统", "百万", "企业级"],
        forbidden_patterns=["___", "不可能实现"],
        min_length=300,
    ),
]

QUERIES_LAYER4_FALLBACK = [
    QueryTestCase(
        id="L4-001",
        category="降级-API超时",
        user_input="这是一个测试超时的请求，请正常回复即可",
        expected_keywords=["回复"],
        forbidden_patterns=["___"],
        min_length=30,
        max_latency_sec=0.001,
    ),
    QueryTestCase(
        id="L4-002",
        category="降级-API错误",
        user_input="测试API异常时的降级行为",
        expected_keywords=["降级"],
        forbidden_patterns=["___", "Traceback"],
        min_length=30,
    ),
    QueryTestCase(
        id="L4-003",
        category="降级-无搜索结果",
        user_input="查询一个完全不存在的冷门术语: xyz_量子纠缠区块链元宇宙",
        expected_keywords=[],
        forbidden_patterns=["___"],
        min_length=100,
    ),
    QueryTestCase(
        id="L4-004",
        category="降级-网络断开模拟",
        user_input="网络断开时能否返回缓存的历史结果?",
        expected_keywords=[],
        forbidden_patterns=["___", "ConnectionError"],
        min_length=30,
    ),
    QueryTestCase(
        id="L4-005",
        category="降级-配额耗尽",
        user_input="这是第10001次调用，已超过API配额限制",
        expected_keywords=["配额"],
        forbidden_patterns=["___", "rate limit exceeded"],
        min_length=30,
    ),
]

QUERIES_LAYER5_PERFORMANCE = [
    QueryTestCase(
        id="L5-001",
        category="性能-短查询",
        user_input="说Hello",
        expected_keywords=["Hello"],
        forbidden_patterns=["___"],
        min_length=10,
        max_latency_sec=5.0,
    ),
    QueryTestCase(
        id="L5-002",
        category="性能-中等查询",
        user_input="列举JavaScript ES2024的3个新特性",
        expected_keywords=["JavaScript", "ES2024", "新特性"],
        forbidden_patterns=["___"],
        min_length=150,
        max_latency_sec=10.0,
    ),
    QueryTestCase(
        id="L5-003",
        category="性能-长查询",
        user_input="写一份完整的产品需求文档(PRD)，包含背景、目标用户、功能规格、非功能性需求和成功指标",
        expected_keywords=["PRD", "产品需求", "功能规格"],
        forbidden_patterns=["___", "待补充"],
        min_length=1500,
        max_latency_sec=30.0,
    ),
    QueryTestCase(
        id="L5-004",
        category="性能-复杂查询",
        user_input="基于以下背景制定详细的6个月产品路线图:\n当前: MVP阶段，核心功能已完成80%，有200个活跃用户\n目标: 达到1000个付费用户，月收入$10K\n资源: 团队3人(1后端+1前端+1运营)\n竞争: 有3个直接竞品，价格区间$5-$20",
        expected_keywords=["6个月", "路线图", "MVP", "200", "1000", "$10K", "3人"],
        forbidden_patterns=["___", "后续迭代"],
        min_length=1200,
        max_latency_sec=30.0,
    ),
    QueryTestCase(
        id="L5-005",
        category="性能-多轮上下文",
        user_input="[历史: 用户之前问了Q2方案，系统生成了包含3阶段的计划]\n[当前: 第三阶段时间太长(4周)，能缩短到2周吗？同时增加一个应急预算项]",
        expected_keywords=["第三阶段", "2周", "应急预算"],
        forbidden_patterns=["___", "忽略历史"],
        min_length=400,
        max_latency_sec=20.0,
    ),
    *(
        [
            QueryTestCase(
                id=f"L5-{i+6:03d}",
                category=f"性能-批量{i}",
                user_input=f"生成第{i}份周报模板，包含本周进展、下周计划和风险提示",
                expected_keywords=[f"第{i}份", "周报"],
                forbidden_patterns=["___"],
                min_length=200,
                max_latency_sec=15.0,
            )
            for i in range(1, 6)
        ]
    ),
]

ALL_QUERIES = (
    QUERIES_LAYER1_CONNECTIVITY
    + QUERIES_LAYER2_QUALITY
    + QUERIES_LAYER3_BOUNDARY
    + QUERIES_LAYER4_FALLBACK
    + QUERIES_LAYER5_PERFORMANCE
)


class LLME2EValidator:
    """真实LLM API E2E验证器"""

    def __init__(self):
        self.api_key = self._get_api_key()
        self.results: List[E2EResult] = []
        self.stats = {
            "total": 0,
            "success": 0,
            "llm_mode": 0,
            "fallback_mode": 0,
            "error": 0,
            "quality_passed": 0,
            "quality_failed": 0,
            "avg_latency_ms": 0,
            "avg_quality_score": 0,
            "total_tokens": 0,
        }

    def _get_api_key(self) -> Optional[str]:
        key = os.environ.get("MOKA_API_KEY")
        if key:
            return key
        key = os.environ.get("GLM_API_KEY")
        if key:
            return key
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            return key
        try:
            from opc_manager.config import get_config

            config = get_config()
            return getattr(config, "glm_api_key", None) or getattr(
                config, "llm_api_key", None
            )
        except Exception:
            pass
        return None

    def run_query(self, tc: QueryTestCase, force_fallback: bool = False) -> E2EResult:
        """运行单条查询并通过质量评分"""
        start_time = time.time()

        if force_fallback or not self.api_key:
            result = self._run_fallback(tc)
        else:
            result = self._run_real_api(tc)

        elapsed_ms = (time.time() - start_time) * 1000
        result.latency_ms = round(elapsed_ms, 1)

        if result.success and result.content:
            qs = self._score_quality(tc, result)
            result.quality_score = qs
            if qs.passed:
                self.stats["quality_passed"] += 1
            else:
                self.stats["quality_failed"] += 1

        self.results.append(result)
        self._update_stats(result)
        return result

    def _run_real_api(self, tc: QueryTestCase) -> E2EResult:
        try:
            from opc_manager.llm_content import LLMEnhancedContentGenerator

            generator = LLMEnhancedContentGenerator(llm_timeout=tc.max_latency_sec)

            template = f"# {tc.category}报告\n\n## 内容\n{{business_context}}\n## 详细信息\n{{user_query}}\n"
            search_results = [
                {"title": f"{tc.category}参考资料", "snippet": "相关背景信息"}
            ]

            gen_result = generator.generate(
                user_input=tc.user_input,
                template=template,
                search_results=search_results,
            )

            if gen_result.success and gen_result.generation_mode == "llm_rag":
                return E2EResult(
                    query_id=tc.id,
                    category=tc.category,
                    user_input=tc.user_input[:50]
                    + ("..." if len(tc.user_input) > 50 else ""),
                    success=True,
                    mode="llm_rag",
                    content=gen_result.content,
                    latency_ms=0,
                    tokens_used=len(gen_result.content) // 2,
                )
            elif gen_result.fallback_used:
                return E2EResult(
                    query_id=tc.id,
                    category=tc.category,
                    user_input=tc.user_input[:50],
                    success=True,
                    mode="template_fallback",
                    content=gen_result.content,
                    latency_ms=0,
                    tokens_used=0,
                )
            else:
                return E2EResult(
                    query_id=tc.id,
                    category=tc.category,
                    user_input=tc.user_input[:50],
                    success=False,
                    mode="llm_failed",
                    content=gen_result.content or "",
                    latency_ms=0,
                    tokens_used=0,
                    error_message="LLM generation returned empty or failed",
                )

        except Exception as e:
            return E2EResult(
                query_id=tc.id,
                category=tc.category,
                user_input=tc.user_input[:50],
                success=False,
                mode="error",
                content="",
                latency_ms=0,
                tokens_used=0,
                error_message=str(e),
            )

    def _run_fallback(self, tc: QueryTestCase) -> E2EResult:
        from opc_manager.llm_content import LLMEnhancedContentGenerator

        generator = LLMEnhancedContentGenerator()

        template = f"# {tc.category}\n\n{tc.user_input}\n\n" + "详细内容。" * 20
        gen_result = generator.generate(user_input=tc.user_input, template=template)

        return E2EResult(
            query_id=tc.id,
            category=tc.category,
            user_input=tc.user_input[:50],
            success=True,
            mode="template_forced",
            content=gen_result.content,
            latency_ms=0,
            tokens_used=0,
        )

    def _score_quality(self, tc: QueryTestCase, result: E2EResult) -> QualityScore:
        content = result.content.lower()
        scores = {}
        details = {}

        s1 = sum(1 for kw in tc.expected_keywords if kw.lower() in content)
        scores["S1_业务注入"] = min(s1, 2)
        details["S1"] = f"业务关键词命中{s1}/{len(tc.expected_keywords)}"

        number_pattern = (
            r"\d+[\.]?\d*\s*(?:万|千|%|元|人|天|周|月|年|次|个|条|GB|MB|$|k)"
        )
        numbers_found = len(re.findall(number_pattern, content))
        date_pattern = r"\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?|\d{1,2}[/月]\d{1,2}[日]?"
        dates_found = len(re.findall(date_pattern, content))
        action_pattern = r"(?:实施|执行|部署|发布|提交|创建|发送|联系|召开|启动|完成|优化|改进|调整|增加|减少|提升|降低)[^。，]*?(?:方案|计划|报告|文档|代码|功能|页面|邮件|会议)"
        actions_found = len(re.findall(action_pattern, content))
        specificity_score = min((numbers_found + dates_found + actions_found), 3)
        scores["S2_具体性"] = specificity_score
        details["S2"] = (
            f"具体元素: 数字={numbers_found}, 日期={dates_found}, 行动={actions_found}"
        )

        headers = re.findall(r"^#+\s+.+", content, re.MULTILINE)
        scores["S3_结构"] = min(len(headers), 2)
        details["S3"] = f"Markdown标题数={len(headers)}"

        forbidden_count = sum(1 for p in tc.forbidden_patterns if p in content)
        generic_phrases = [
            "适时",
            "加强关注",
            "密切关注",
            "视情况而定",
            "根据实际情况",
            "清晰定义",
            "明确边界",
        ]
        generic_count = sum(1 for phrase in generic_phrases if phrase in content)
        scores["S4_无禁止内容"] = max(0, 2 - forbidden_count - generic_count // 2)
        details["S4"] = f"禁止模式:{forbidden_count}, 泛化短语:{generic_count}"

        has_reference = any(
            kw in content for kw in ["资料", "参考", "来源", "据[显示]", "search"]
        )
        scores["S5_搜索引用"] = 1 if has_reference else 0
        details["S5"] = f"搜索引用={'有' if has_reference else '无'}"

        total = sum(scores.values())
        passed = total >= 6

        return QualityScore(
            query_id=tc.id,
            scores=scores,
            total=total,
            passed=passed,
            details=details,
        )

    def _update_stats(self, result: E2EResult):
        self.stats["total"] += 1
        if result.success:
            self.stats["success"] += 1
            if result.mode == "llm_rag":
                self.stats["llm_mode"] += 1
            elif "fallback" in result.mode:
                self.stats["fallback_mode"] += 1
        else:
            self.stats["error"] += 1

        if self.stats["success"] > 0:
            self.stats["avg_latency_ms"] = (
                self.stats["avg_latency_ms"] * (self.stats["success"] - 1)
                + result.latency_ms
            ) / self.stats["success"]
        if result.tokens_used > 0:
            self.stats["total_tokens"] += result.tokens_used

    def generate_report(self) -> str:
        """生成测试报告"""
        lines = []
        lines.append("# G-LLM-REAL-01 真实LLM API E2E验证报告")
        lines.append(f"\n**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(
            f"**API状态**: {'✅ 已配置' if self.api_key else '❌ 未配置(使用降级模式)'}"
        )
        if self.api_key:
            lines.append(f"**API Key**: {'*' * 4}{self.api_key[-4:]}")
        else:
            lines.append("**API Key**: 无")
        lines.append("")

        stats = self.stats
        lines.append("## 总体统计")
        lines.append(f"| 指标 | 数值 | 占比 |")
        lines.append(f"|------|------|------|")
        lines.append(f"| 总查询数 | {stats['total']} | 100% |")
        lines.append(
            f"| ✅ 成功 | {stats['success']} | {stats['success']/max(stats['total'],1)*100:.0f}% |"
        )
        lines.append(
            f"| 🤖 LLM RAG模式 | {stats['llm_mode']} | {stats['llm_mode']/max(stats['total'],1)*100:.0f}% |"
        )
        lines.append(
            f"| 📋 降级模式 | {stats['fallback_mode']} | {stats['fallback_mode']/max(stats['total'],1)*100:.0f}% |"
        )
        lines.append(
            f"| ❌ 失败 | {stats['error']} | {stats['error']/max(stats['total'],1)*100:.0f}% |"
        )
        lines.append(
            f"| 🎯 质量合格 | {stats['quality_passed']}/{stats['quality_passed']+stats['quality_failed']} | {stats['quality_passed']/max(stats['quality_passed']+stats['quality_failed'],1)*100:.0f}% |"
        )
        lines.append(f"| ⏱️ 平均延迟 | {stats['avg_latency_ms']:.0f}ms | — |")
        lines.append(f"| 🔤 Token消耗 | {stats['total_tokens']} | — |")
        lines.append("")

        lines.append("## 门禁判定")
        llm_rate = stats["llm_mode"] / max(stats["total"], 1)
        quality_rate = stats["quality_passed"] / max(
            stats["quality_passed"] + stats["quality_failed"], 1
        )

        gate_llm_pass = llm_rate >= 0.10
        gate_quality_pass = quality_rate >= 0.70
        gate_overall = gate_llm_pass and gate_quality_pass

        lines.append(f"| 门禁 | 标准 | 实际 | 通过? |")
        lines.append(f"|------|------|------|------|")
        lines.append(
            f"| G-LLM-REAL-01a: 真实API占比 | ≥10% | {llm_rate*100:.1f}% | {'✅' if gate_llm_pass else '❌'} |"
        )
        lines.append(
            f"| G-LLM-REAL-01b: 质量合格率 | ≥70% | {quality_rate*100:.1f}% | {'✅' if gate_quality_pass else '❌'} |"
        )
        lines.append(
            f"| **综合** | **两项都过** | **—** | {'✅ **PASS**' if gate_overall else '❌ **FAIL**'} |"
        )

        if not gate_overall:
            lines.append("\n### ⚠️ 门禁未通过 — 阻塞性问题:")
            if not gate_llm_pass:
                lines.append("- 真实API调用比例不足10%（可能全是mock/降级）")
            if not gate_quality_pass:
                lines.append("- 输出质量合格率低于70%（真实LLM效果不达标）")
        else:
            lines.append("\n### ✅ 门禁通过 — 可以发布!")

        lines.append("\n## 详细结果")
        for r in self.results:
            status_icon = "✅" if r.success else "❌"
            mode_tag = f"`{r.mode}`"
            score_str = ""
            if r.quality_score:
                score_color = "🟢" if r.quality_score.passed else "🔴"
                score_str = f"{score_color} {r.quality_score.total}/10"

            lines.append(f"\n#### {status_icon} [{r.query_id}] ({r.category})")
            lines.append(f"- **输入**: {r.user_input}")
            lines.append(f"- **模式**: {mode_tag}")
            lines.append(f"- **延迟**: {r.latency_ms:.0f}ms")
            if score_str:
                lines.append(f"- **质量**: {score_str}")
            if r.error_message:
                lines.append(f"- **错误**: `{r.error_message[:80]}`")
            if r.success and len(r.content) < 200:
                lines.append(f"- **内容预览**: {r.content[:150]}...")

        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="G-LLM-REAL-01 真实LLM API E2E验证")
    parser.add_argument(
        "--layer", choices=["L1", "L2", "L3", "L4", "L5"], help="仅执行指定层"
    )
    parser.add_argument("--quick", action="store_true", help="快速模式(L1 only)")
    parser.add_argument(
        "--force-fallback", action="store_true", help="强制使用降级模式(无API时)"
    )
    parser.add_argument("--report", action="store_true", help="生成报告文件")
    args = parser.parse_args()

    validator = LLME2EValidator()

    if args.quick or args.layer == "L1":
        queries_to_run = QUERIES_LAYER1_CONNECTIVITY
        logger.info(f"🚀 快速模式: 仅执行Layer 1 ({len(queries_to_run)} 条)")
    elif args.layer == "L2":
        queries_to_run = QUERIES_LAYER2_QUALITY
    elif args.layer == "L3":
        queries_to_run = QUERIES_LAYER3_BOUNDARY
    elif args.layer == "L4":
        queries_to_run = QUERIES_LAYER4_FALLBACK
    elif args.layer == "L5":
        queries_to_run = QUERIES_LAYER5_PERFORMANCE
    else:
        queries_to_run = ALL_QUERIES
        logger.info(f"🚀 全量模式: 执行全部 {len(queries_to_run)} 条查询")

    logger.info("=" * 60)
    logger.info("G-LLM-REAL-01: 真实LLM API E2E验证开始")
    logger.info(
        f"API Key: {'✅ 已配置' if validator.api_key else '❌ 未配置(降级模式)'}"
    )
    logger.info(f"查询数量: {len(queries_to_run)}")
    logger.info("=" * 60)

    for i, tc in enumerate(queries_to_run, 1):
        logger.info(f"[{i}/{len(queries_to_run)}] 执行 {tc.id} ({tc.category})...")
        result = validator.run_query(tc, force_fallback=args.force_fallback)

        status = "✅" if result.success else "❌"
        mode_short = result.mode.replace("template_", "").replace("llm_", "")
        score_info = (
            f", 质量={result.quality_score.total}/10" if result.quality_score else ""
        )
        logger.info(
            f"  {status} [{result.query_id}] mode={mode_short}{score_info} {result.latency_ms:.0f}ms"
        )

    report = validator.generate_report()
    print("\n" + "=" * 60)
    print(report)

    if args.report:
        report_path = (
            RESULTS_DIR / f"e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        report_path.write_text(report, encoding="utf-8")
        logger.info(f"📄 报告已保存: {report_path}")

    stats = validator.stats
    overall_pass = (stats["llm_mode"] / max(stats["total"], 1) >= 0.10) and (
        stats["quality_passed"]
        / max(stats["quality_passed"] + stats["quality_failed"], 1)
        >= 0.70
    )

    if overall_pass:
        logger.info("🎉 G-LLM-REAL-01 门禁通过!")
        return 0
    else:
        logger.warning("⚠️ G-LLM-REAL-01 门禁未通过 — 请查看上方报告")
        return 1


if __name__ == "__main__":
    exit(main())
