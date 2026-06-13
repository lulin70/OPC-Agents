"""
Business Type Detector - BusinessTypeDetector V2

Phase 2 Enhanced: Improve accuracy from 80% to 95%+
New features:
- Pattern recognition (common expression patterns)
- Negation detection (avoid misclassification)
- Context awareness (conversation history weighting)
- Synonym expansion
- LLM assistance interface (reserved)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import re
import logging

from opc_manager.business_types import BusinessType

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Detection result"""

    business_type: BusinessType
    confidence: float
    method: str  # "pattern_match", "keyword_match", "profile_inference", "history_analysis", "llm_assisted", "default"
    matched_keywords: List[str] = field(default_factory=list)
    alternative_types: List[Tuple[BusinessType, float]] = field(default_factory=list)
    detected_patterns: List[str] = field(default_factory=list)
    reasoning: str = ""


class BusinessTypeDetectorV2:
    """
    Business Type Detector V2 (Phase 2 Enhanced)

    Detection strategy priority:
    1. Pattern matching (highest priority) - Identify specific expression patterns
    2. Keyword matching (main strategy) - Extract feature words from user input
    3. Context analysis (auxiliary) - Analyze patterns in conversation history
    4. User profile inference (auxiliary) - If user has saved type preference
    5. LLM assistance (optional) - Call large model for semantic understanding
    6. Default fallback - If all above fail, return default type

    Phase 2 improvements:
    - Accuracy target: 95%+ (up from 80%)
    - Added pattern recognition capability
    - Added negation detection mechanism
    - Added context awareness
    - Added synonym expansion
    """

    def __init__(self, enable_llm: bool = False, llm_service=None):
        """
        Initialize Detector V2

        Args:
            enable_llm: Whether to enable LLM-assisted detection (requires API Key)
            llm_service: LLM service instance (Phase 3 addition, supports external injection)
        """
        self.type_keywords = self._init_keyword_database_v2()
        self.patterns = self._init_pattern_database()
        self.negation_words = {"不", "不是", "没有", "别", "不要", "非", "无", "没"}
        self.default_type = BusinessType.CONTENT_CREATOR
        self.confidence_threshold = 0.12
        self.enable_llm = enable_llm
        self.llm_service = llm_service
        self._stats = {"total_detections": 0, "method_distribution": {}}

    def _init_keyword_database_v2(self) -> Dict[BusinessType, Dict[str, Any]]:
        """
        Initialize enhanced keyword database V2

        Improvements over V1:
        - Expanded primary_keywords (25-35 per type)
        - Added synonyms (synonym mapping)
        - Added domain_phrases (domain-specific phrases)
        - Optimized weight values based on actual test data
        """
        return {
            BusinessType.CONTENT_CREATOR: {
                "name": "内容创作者",
                "emoji": "✍️",
                "weight": 1.6,
                "primary_keywords": [
                    "内容",
                    "创作",
                    "写作",
                    "文章",
                    "博客",
                    "公众号",
                    "小红书",
                    "抖音",
                    "视频",
                    "直播",
                    "UP主",
                    "博主",
                    "粉丝",
                    "涨粉",
                    "爆款",
                    "选题",
                    "日历",
                    "排期",
                    "种草",
                    "完播率",
                    "互动率",
                    "阅读量",
                    "10万+",
                    "流量",
                    "变现",
                    "广告",
                    "品牌合作",
                    "MCN",
                    "笔记",
                    "图文",
                    "短视频",
                    "中视频",
                    "长视频",
                    "投流",
                    "达人",
                    "KOL",
                    "KOC",
                    "矩阵",
                ],
                "secondary_keywords": [
                    "发布",
                    "更新",
                    "推送",
                    "素材",
                    "文案",
                    "标题",
                    "封面",
                    "脚本",
                    "拍摄",
                    "剪辑",
                    "平台",
                    "算法",
                    "推荐",
                    "热搜",
                    "话题",
                    "点赞",
                    "评论",
                    "转发",
                    "收藏",
                    "分享",
                    "粉丝画像",
                    "用户画像",
                    "账号运营",
                ],
                "context_phrases": [
                    "帮我写一篇",
                    "下周发什么",
                    "内容规划",
                    "粉丝画像",
                    "多平台",
                    "矩阵运营",
                    "我的小红书",
                    "我的抖音",
                    "涨粉技巧",
                ],
                "synonyms": {
                    "内容创作": ["自媒体", "新媒体", "内容生产"],
                    "爆款": ["爆文", "热门", " viral"],
                    "粉丝": ["关注者", "订阅者", "读者"],
                },
                "domain_phrases": [
                    "选题库",
                    "热点追踪",
                    "内容分发",
                    "流量池",
                    "私域流量",
                    "公域流量",
                    "账号权重",
                    "垂直度",
                ],
            },
            BusinessType.DIGITAL_PRODUCT: {
                "name": "数字产品开发者",
                "emoji": "💰",
                "weight": 1.4,
                "primary_keywords": [
                    "数字产品",
                    "知识付费",
                    "课程",
                    "电子书",
                    "模板",
                    "小报童",
                    "Gumroad",
                    "Teachable",
                    "产品上架",
                    "定价",
                    "销售页",
                    "landing page",
                    "漏斗",
                    "付费用户",
                    "订阅",
                    "会员",
                    "社群",
                    "知识星球",
                    "专栏",
                    "训练营",
                    "SaaS",
                    "工具",
                    "插件",
                    "Notion模板",
                    "Excel模板",
                    "PPT模板",
                    "付费阅读",
                    "付费社群",
                    "会员制",
                ],
                "secondary_keywords": [
                    "售卖",
                    "收入",
                    "营收",
                    "转化率",
                    "客单价",
                    "复购",
                    "续费",
                    "退款",
                    "评价",
                    "评分",
                    "产品包装",
                    "USP",
                    "卖点",
                    "价值主张",
                    "预售",
                    "早鸟价",
                    "限时优惠",
                    "满减",
                ],
                "context_phrases": [
                    "我要卖",
                    "如何定价",
                    "写销售页",
                    "产品发布",
                    "上线",
                    "推广课程",
                    "在Gumroad上",
                    "在Teachable上",
                    "知识变现",
                ],
                "synonyms": {
                    "数字产品": ["虚拟产品", "信息产品", "在线课程"],
                    "知识付费": ["知识变现", "付费内容", "付费社群"],
                    "销售页": ["落地页", "Landing Page", "详情页"],
                },
                "domain_phrases": [
                    "价值阶梯",
                    "后端销售",
                    "Upsell",
                    "Cross-sell",
                    "客户终身价值",
                    "LTV",
                    "CAC",
                    "MRR",
                    "ARR",
                ],
            },
            BusinessType.AI_TOOL_BUILDER: {
                "name": "AI工具开发者",
                "emoji": "🤖",
                "weight": 1.5,
                "primary_keywords": [
                    "AI工具",
                    "人工智能",
                    "API",
                    "GPT",
                    "LLM",
                    "ChatGPT",
                    "Claude",
                    "模型",
                    "训练",
                    "微调",
                    "应用",
                    "插件",
                    "扩展",
                    "Agent",
                    "智能助手",
                    "自动化",
                    "代码",
                    "开源",
                    "GitHub",
                    "部署",
                    "用户反馈",
                    "评论",
                    "Issues",
                    "PR",
                    "版本",
                    "功能",
                    "迭代",
                    "路线图",
                    "roadmap",
                    "SDK",
                    "Latency",
                    "Throughput",
                    "Scalability",
                    "Tech Debt",
                    "Refactor",
                    "Deploy",
                    "CI/CD",
                ],
                "secondary_keywords": [
                    "技术文档",
                    "SDK",
                    "集成",
                    "接口",
                    "Token",
                    "调用",
                    "延迟",
                    "性能",
                    "优化",
                    "Bug",
                    "Feature Request",
                    "Changelog",
                    "Release",
                    "Docker",
                    "Kubernetes",
                    "Microservice",
                    "RESTful",
                    "GraphQL",
                    "Webhook",
                    "Rate Limiting",
                    "Caching",
                ],
                "context_phrases": [
                    "我的工具",
                    "用户说",
                    "App Store评论",
                    "GitHub Issues",
                    "新功能",
                    "版本更新",
                    "我的API",
                    "我的应用",
                    "我的产品",
                ],
                "synonyms": {
                    "AI工具": ["人工智能应用", "智能软件", "AI产品"],
                    "API": ["接口", "SDK", "开发包"],
                    "部署": ["上线", "发布", "发布到生产环境"],
                },
                "domain_phrases": [
                    "RICE评分",
                    "MoSCoW法则",
                    "Kano模型",
                    "OKR",
                    "Agile",
                    "Scrum",
                    "Code Review",
                    "TDD",
                    "单元测试",
                    "集成测试",
                    "端到端测试",
                ],
            },
            BusinessType.CONSULTANT: {
                "name": "专业咨询师",
                "emoji": "💼",
                "weight": 1.3,
                "primary_keywords": [
                    "咨询",
                    "顾问",
                    "提案",
                    "建议书",
                    "方案",
                    "客户",
                    "项目",
                    "服务",
                    "专业",
                    "专家",
                    "战略",
                    "规划",
                    "分析",
                    "研究",
                    "报告",
                    "演示",
                    "汇报",
                    "PPT",
                    "交付物",
                    "合同",
                    "报价",
                    "费用",
                    "时薪",
                    "按项目",
                    "retainer",
                    "方法论",
                    "框架",
                    "SWOT",
                    "PESTEL",
                    "商业模式画布",
                    "价值链分析",
                ],
                "secondary_keywords": [
                    "行业",
                    "市场",
                    "竞争",
                    "痛点",
                    "需求",
                    "解决方案",
                    "最佳实践",
                    "案例",
                    "经验",
                    "洞察",
                    "利益相关者",
                    "Stakeholder",
                    "里程碑",
                    "KPI",
                    "ROI",
                    "投资回报",
                    "验收标准",
                ],
                "context_phrases": [
                    "我的客户",
                    "给客户写",
                    "咨询项目",
                    "服务报价",
                    "专业建议",
                    "客户要做",
                    "帮客户",
                    "为甲方",
                ],
                "synonyms": {
                    "咨询": ["顾问服务", "专业服务", "咨询服务"],
                    "提案": ["建议书", "方案书", "Project Proposal"],
                    "报价": ["费用估算", "价格方案", "Quotation"],
                },
                "domain_phrases": [
                    "SMART原则",
                    "RACI矩阵",
                    "PDCA循环",
                    "五力模型",
                    "BCG矩阵",
                    "安索夫矩阵",
                    "价值主张设计",
                    "精益画布",
                ],
            },
            BusinessType.ECOMMERCE: {
                "name": "电商运营者",
                "emoji": "🛒",
                "weight": 1.4,
                "primary_keywords": [
                    "电商",
                    "淘宝",
                    "天猫",
                    "京东",
                    "拼多多",
                    "店铺",
                    "商品",
                    "SKU",
                    "库存",
                    "订单",
                    "发货",
                    "物流",
                    "快递",
                    "GMV",
                    "销售额",
                    "转化率",
                    "客单价",
                    "访客",
                    "UV",
                    "PV",
                    "直通车",
                    "钻展",
                    "促销",
                    "活动",
                    "双十一",
                    "618",
                    "直播带货",
                    "供应链",
                    "选品",
                    "DSR",
                    "动销率",
                    "复购率",
                    "退货率",
                    "问大家",
                    "好评率",
                    "发货时效",
                ],
                "secondary_keywords": [
                    "详情页",
                    "主图",
                    "标题优化",
                    "SEO",
                    "评价",
                    "退款",
                    "售后",
                    "客服",
                    "旺信",
                    "聚划算",
                    "秒杀",
                    "满减",
                    "优惠券",
                    "红包",
                    "达人带货",
                    "直播间",
                    "品销宝",
                    "超级推荐",
                ],
                "context_phrases": [
                    "我的店铺",
                    "商品上架",
                    "活动报名",
                    "库存预警",
                    "订单处理",
                    "我的淘宝店",
                    "我的京东店",
                    "在拼多多上",
                ],
                "synonyms": {
                    "电商": ["网店", "线上店铺", "电子商务"],
                    "店铺": ["旗舰店", "专营店", "专卖店"],
                    "选品": ["商品开发", "产品开发", "Product Sourcing"],
                },
                "domain_phrases": [
                    "引力魔方",
                    "生意参谋",
                    "数据银行",
                    "人群画像",
                    "投放ROI",
                    "点击率(CTR)",
                    "收藏加购率",
                    "转化漏斗",
                ],
            },
            BusinessType.CREATIVE_WORK: {
                "name": "创意工作者",
                "emoji": "🎨",
                "weight": 1.3,
                "primary_keywords": [
                    "设计",
                    "创意",
                    "作品",
                    "交付",
                    "客户",
                    "UI",
                    "UX",
                    "平面",
                    "品牌",
                    "logo",
                    "插画",
                    "摄影",
                    "视频制作",
                    "剪辑",
                    "作品集",
                    "portfolio",
                    "提案",
                    "样机",
                    "Figma",
                    "Sketch",
                    "Photoshop",
                    "AI绘画",
                    "Midjourney",
                    "Stable Diffusion",
                    "DALL-E",
                    "排版",
                    "配色",
                    "字体",
                    "图标",
                    "视觉",
                    "品牌VI",
                    "包装设计",
                    "海报",
                    "H5页面",
                ],
                "secondary_keywords": [
                    "视觉",
                    "配色",
                    "排版",
                    "字体",
                    "图标",
                    "原型",
                    "交互",
                    "动效",
                    "渲染",
                    "素材",
                    "版权",
                    "商用",
                    "授权",
                    "样机",
                    "Mockup",
                    "Design System",
                    "Style Guide",
                ],
                "context_phrases": [
                    "设计稿",
                    "效果图",
                    "客户反馈",
                    "作品集整理",
                    "创意方案",
                    "我的设计",
                    "帮做个logo",
                    "设计个海报",
                ],
                "synonyms": {
                    "设计": ["Design", "视觉设计", "平面设计"],
                    "作品集": ["Portfolio", "案例集", "作品展示"],
                    "交付": ["交付物", "Final Delivery", "终稿"],
                },
                "domain_phrases": [
                    "极简主义",
                    "孟菲斯风格",
                    "赛博朋克",
                    "日式禅意",
                    "北欧风",
                    "波普艺术",
                    "扁平化",
                    "新拟态",
                    "玻璃拟态",
                ],
            },
        }

    def _init_pattern_database(self) -> Dict[BusinessType, List[str]]:
        """
        Initialize pattern database

        Patterns are higher-order expression forms than keywords,
        capturing specific grammatical structures and semantic intent
        """
        return {
            BusinessType.CONTENT_CREATOR: [
                r"帮我写.*?(文章|笔记|文案|内容)",
                r"(小红书|抖音|公众号|B站).*(运营|管理|规划)",
                r".*?(涨粉|增粉|吸粉).*?",
                r".*?(爆款|爆文|10万\+).*?",
                r".*?(选题|内容日历|排期).*?",
                r"我的.*(账号|博主|UP主)",
            ],
            BusinessType.DIGITAL_PRODUCT: [
                r"(售卖|出售|上架).*(课程|电子书|模板|产品)",
                r"(Gumroad|Teachable|小报童|知识星球).*(发布|上架|开设)",
                r".*?(定价|价格|收费).*?(课程|产品|内容)",
                r".*?(销售页|Landing Page|详情页).*?(撰写|优化|设计)",
                r".*?(知识付费|付费内容|付费社群).*?",
            ],
            BusinessType.AI_TOOL_BUILDER: [
                r"(我的|开发|构建).*(工具|应用|API|产品).*(AI|人工智能|GPT|LLM)",
                r".*?(App Store|GitHub|Product Hunt).*(评论|反馈|Issues)",
                r".*?(版本|迭代|更新|发布).*(日志|说明|Notes)",
                r".*?(性能|优化|延迟|Latency|速度).*?(提升|改进|优化)",
                r".*?(用户反馈|User Feedback|评论).*?(分析|处理|回复)",
            ],
            BusinessType.CONSULTANT: [
                r"(给|为|帮).*(客户|甲方).*(写|做|起草).*?(方案|报告|提案|建议书)",
                r".*?(咨询|顾问|专家).*?(服务|项目|报价)",
                r".*?(SWOT|PESTEL|商业模式|战略).*?(分析|规划|制定)",
                r".*?(报价|费用|时薪|预算).*?(方案|明细|清单)",
                r".*?(方法论|框架|模型).*?(应用|使用|实施)",
            ],
            BusinessType.ECOMMERCE: [
                r"(我的|帮).*(店铺|淘宝|京东|拼多多).*(运营|管理|优化)",
                r".*?(商品|产品|SKU).*(上架|发布|编辑|优化)",
                r".*?(促销|活动|大促|双十一|618).*(策划|方案|准备)",
                r".*?(库存|补货|供应链).*(预警|管理|优化)",
                r".*?(GMV|销售额|转化率|ROI).*(提升|分析|优化)",
            ],
            BusinessType.CREATIVE_WORK: [
                r"(帮我|给我).*(设计|做|画|创.*?作).*(logo|海报|UI|界面|插画|图片)",
                r".*?(Figma|Sketch|Photoshop|AI绘画|Midjourny).*?(文件|源件|设计稿)",
                r".*?(作品集|Portfolio|案例).*?(整理|更新、优化)",
                r".*?(设计稿|效果图|样机).*(交付|提交|发送)",
                r".*?(品牌|VI|视觉).*(设计|升级、规范)",
            ],
        }

    def detect(
        self,
        input_text: str,
        user_profile: Optional[Dict] = None,
        history: Optional[List[Dict]] = None,
        min_confidence: float = None,
    ) -> DetectionResult:
        """
        Detect user's business type (V2 Enhanced)

        Args:
            input_text: User input text
            user_profile: User profile info (optional)
            history: Conversation history (optional)
            min_confidence: Minimum confidence threshold (optional)

        Returns:
            DetectionResult: Contains detection result and reasoning process
        """
        if min_confidence is None:
            min_confidence = self.confidence_threshold

        self._stats["total_detections"] += 1

        # Step 1: Pattern matching (highest priority)
        pattern_result = self._detect_by_pattern(input_text)
        if pattern_result and pattern_result.confidence >= 0.8:
            self._record_method("pattern_match")
            return self._build_result(
                pattern_result.business_type,
                pattern_result.confidence,
                "pattern_match",
                input_text,
                detected_patterns=pattern_result.detected_patterns,
            )

        # Step 2: Keyword matching (main strategy)
        keyword_result = self._detect_by_keywords(input_text)

        # Step 3: Negation detection (reduce misclassification)
        if self._contains_negation(input_text):
            keyword_result = self._adjust_for_negation(keyword_result, input_text)

        # Step 4: Context analysis (if history exists)
        if history and len(history) >= 3:
            context_boost = self._analyze_context(history)
            keyword_result = self._apply_context_boost(keyword_result, context_boost)

        # Step 5: User profile inference (if available)
        if user_profile and keyword_result.confidence < 0.6:
            profile_type = self._infer_from_profile(user_profile)
            if profile_type and keyword_result.business_type != profile_type:
                if keyword_result.confidence < 0.4:
                    keyword_result = self._build_result(
                        profile_type, 0.55, "profile_inference", input_text
                    )
                    self._record_method("profile_inference")

        # Step 6: LLM assistance (if enabled and confidence is low)
        if self.enable_llm and keyword_result.confidence < 0.5:
            try:
                llm_result = self._detect_by_llm(input_text, history)
                if llm_result and llm_result.confidence > keyword_result.confidence:
                    keyword_result = llm_result
                    self._record_method("llm_assisted")
            except Exception as e:
                logger.debug("[BusinessTypeDetectorV2] LLM assist failed: %s", e)

        # Ensure minimum threshold is met
        if keyword_result.confidence < min_confidence:
            if user_profile:
                profile_type = self._infer_from_profile(user_profile)
                if profile_type:
                    keyword_result = self._build_result(
                        profile_type,
                        min_confidence + 0.1,
                        "profile_fallback",
                        input_text,
                    )
                else:
                    keyword_result = self._build_result(
                        self.default_type, 0.2, "default", input_text
                    )
            else:
                keyword_result = self._build_result(
                    self.default_type, 0.2, "default", input_text
                )

        self._record_method("keyword_match")
        return keyword_result

    def _detect_by_pattern(self, input_text: str) -> Optional[DetectionResult]:
        """Detect business type via regex pattern matching"""
        best_match = None
        best_confidence = 0.0
        detected_patterns = []

        for btype, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, input_text, re.IGNORECASE)
                if match:
                    confidence = 0.9  # High confidence for pattern matching
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = btype
                        detected_patterns.append(pattern)

        if best_match:
            return DetectionResult(
                business_type=best_match,
                confidence=min(best_confidence, 0.95),
                method="pattern_match",
                matched_keywords=[],
                alternative_types=[],
                detected_patterns=detected_patterns[:3],
                reasoning=f"Matched {len(detected_patterns)} patterns",
            )

        return None

    def _detect_by_keywords(self, input_text: str) -> DetectionResult:
        """Keyword-based detection (enhanced)"""
        text_lower = input_text.lower().strip()

        scores = {}

        for business_type, keyword_config in self.type_keywords.items():
            score = self._calculate_enhanced_score(text_lower, keyword_config)
            scores[business_type] = score

        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        best_type, best_score = sorted_types[0]

        matched_keywords = self._extract_matched_keywords_enhanced(
            text_lower, self.type_keywords[best_type]
        )

        alternative_types = [
            (bt, score) for bt, score in sorted_types[1:4] if score > 0.08
        ]

        return DetectionResult(
            business_type=best_type,
            confidence=round(best_score, 3),
            method="keyword_match",
            matched_keywords=matched_keywords,
            alternative_types=alternative_types,
            detected_patterns=[],
            reasoning=f"Keyword score: {best_score:.3f}, matched {len(matched_keywords)} keywords",
        )

    def _calculate_enhanced_score(self, text_lower: str, config: Dict) -> float:
        """
        Calculate enhanced score

        V2 improvements:
        - primary_keywords: ×2.5 (was ×2)
        - secondary_keywords: ×1.5 (was ×1)
        - context_phrases: ×4.0 (was ×3)
        - domain_phrases: ×3.0 (new)
        - synonyms: ×1.8 (new)
        - Complete phrase match bonus: +0.15
        """
        primary_matches = sum(
            1 for kw in config.get("primary_keywords", []) if kw.lower() in text_lower
        )

        secondary_matches = sum(
            1 for kw in config.get("secondary_keywords", []) if kw.lower() in text_lower
        )

        context_matches = sum(
            1
            for phrase in config.get("context_phrases", [])
            if phrase.lower() in text_lower
        )

        domain_matches = sum(
            1
            for phrase in config.get("domain_phrases", [])
            if phrase.lower() in text_lower
        )

        synonym_matches = 0
        synonyms = config.get("synonyms", {})
        for base_word, syn_list in synonyms.items():
            if base_word.lower() in text_lower:
                synonym_matches += 1
            else:
                for syn in syn_list:
                    if syn.lower() in text_lower:
                        synonym_matches += 0.7
                        break

        raw_score = (
            primary_matches * 2.5
            + secondary_matches * 1.5
            + context_matches * 4.0
            + domain_matches * 3.0
            + synonym_matches * 1.8
        )

        max_possible = (
            len(config.get("primary_keywords", [])) * 2.5
            + len(config.get("context_phrases", [])) * 4.0
        ) * 0.25

        normalized_score = min(raw_score / max(max_possible, 1), 1.0)

        bonus = 0.0
        for phrase in config.get("context_phrases", []):
            if phrase.lower() in text_lower:
                bonus += 0.05
        bonus = min(bonus, 0.15)

        weighted_score = (normalized_score + bonus) * config.get("weight", 1.0)

        return round(weighted_score, 3)

    def _extract_matched_keywords_enhanced(
        self, text_lower: str, config: Dict
    ) -> List[str]:
        """Extract matched keywords (enhanced, includes synonyms)"""
        matched = []

        all_keyword_sources = [
            config.get("primary_keywords", []),
            config.get("secondary_keywords", []),
            config.get("context_phrases", []),
            config.get("domain_phrases", []),
        ]

        for source in all_keyword_sources:
            for kw in source:
                if kw.lower() in text_lower:
                    if kw not in matched:
                        matched.append(kw)

        synonyms = config.get("synonyms", {})
        for base_word, syn_list in synonyms.items():
            if base_word.lower() in text_lower and base_word not in matched:
                matched.append(base_word)
            else:
                for syn in syn_list:
                    if syn.lower() in text_lower and syn not in matched:
                        matched.append(syn)
                        break

        return matched[:12]

    def _contains_negation(self, text: str) -> bool:
        """Check if text contains negation words"""
        for word in self.negation_words:
            if word in text:
                return True
        return False

    def _adjust_for_negation(
        self, result: DetectionResult, text: str
    ) -> DetectionResult:
        """Adjust result based on negation words"""
        negation_penalty = 0.3
        new_confidence = max(result.confidence - negation_penalty, 0.1)

        return DetectionResult(
            business_type=result.business_type,
            confidence=new_confidence,
            method=result.method + "_with_negation_check",
            matched_keywords=result.matched_keywords,
            alternative_types=result.alternative_types,
            detected_patterns=result.detected_patterns,
            reasoning=f"{result.reasoning} (contains negation, penalty {negation_penalty})",
        )

    def _analyze_context(self, history: List[Dict]) -> Dict[BusinessType, float]:
        """Analyze conversation history context"""
        type_scores = {}

        for item in history[-8:]:
            user_message = (
                item.get("user", "") or item.get("input", "") or item.get("message", "")
            )
            if user_message:
                temp_result = self._detect_by_keywords(user_message)
                bt_key = temp_result.business_type
                if bt_key not in type_scores:
                    type_scores[bt_key] = {"count": 0, "total_confidence": 0.0}
                type_scores[bt_key]["count"] += 1
                type_scores[bt_key]["total_confidence"] += temp_result.confidence

        context_boost = {}
        for bt, data in type_scores.items():
            if data["count"] >= 3:
                avg_conf = data["total_confidence"] / data["count"]
                boost = min(avg_conf * 0.3, 0.2)
                context_boost[bt] = boost

        return context_boost

    def _apply_context_boost(
        self, result: DetectionResult, context_boost: Dict[BusinessType, float]
    ) -> DetectionResult:
        """Apply context boost"""
        if result.business_type in context_boost:
            boost = context_boost[result.business_type]
            new_confidence = min(result.confidence + boost, 1.0)

            return DetectionResult(
                business_type=result.business_type,
                confidence=new_confidence,
                method=result.method + "_context_boosted",
                matched_keywords=result.matched_keywords,
                alternative_types=result.alternative_types,
                detected_patterns=result.detected_patterns,
                reasoning=f"{result.reasoning} (context boost +{boost:.2f})",
            )

        return result

    def _detect_by_llm(
        self, input_text: str, history: Optional[List[Dict]] = None
    ) -> Optional[DetectionResult]:
        """
        LLM-assisted detection (Phase 3 full implementation)

        Uses injected LLMService for business type detection.
        When keyword matching confidence is low, LLM fallback can improve
        recognition accuracy for complex sentences.
        """
        if not self.enable_llm:
            return None

        if self.llm_service is None:
            return None

        try:
            import asyncio

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                self.llm_service.detect_business_type_by_llm(input_text, history)
            )
            loop.close()

            if result.get("business_type") and result["business_type"] != "unknown":
                try:
                    bt = BusinessType(result["business_type"])
                    confidence = float(result.get("confidence", 0.7))
                    reasoning = result.get("reasoning", "")
                    return DetectionResult(
                        business_type=bt,
                        confidence=min(confidence, 0.99),
                        method="llm_assisted",
                        matched_keywords=[],
                        detected_patterns=[],
                        reasoning=f"LLM detection: {reasoning}",
                    )
                except ValueError:
                    pass
            return None
        except Exception as e:
            import logging

            logging.warning(f"[DetectorV2] LLM detection failed: {e}")
            return None

    def _infer_from_profile(self, user_profile: Dict) -> Optional[BusinessType]:
        """Infer business type from user profile"""
        if not user_profile:
            return None

        saved_type_str = user_profile.get("business_type")
        if saved_type_str:
            return BusinessType.from_string(saved_type_str)

        declared_interests = user_profile.get("interests", [])
        if isinstance(declared_interests, list):
            interests_text = " ".join(declared_interests)
            temp_result = self.detect(interests_text)
            if temp_result.confidence > 0.4:
                return temp_result.business_type

        return None

    def _build_result(
        self,
        business_type: BusinessType,
        confidence: float,
        method: str,
        input_text: str,
        matched_keywords: List[str] = None,
        detected_patterns: List[str] = None,
        reasoning: str = "",
    ) -> DetectionResult:
        """Build standardized detection result"""
        if matched_keywords is None:
            config = self.type_keywords.get(business_type, {})
            matched_keywords = self._extract_matched_keywords_enhanced(
                input_text.lower(), config
            )

        if detected_patterns is None:
            detected_patterns = []

        alternative_types = []
        for bt in self.type_keywords.keys():
            if bt != business_type:
                config = self.type_keywords[bt]
                score = self._calculate_enhanced_score(input_text.lower(), config)
                if score > 0.08:
                    alternative_types.append((bt, round(score, 3)))

        alternative_types.sort(key=lambda x: x[1], reverse=True)
        alternative_types = alternative_types[:3]

        return DetectionResult(
            business_type=business_type,
            confidence=confidence,
            method=method,
            matched_keywords=matched_keywords,
            alternative_types=alternative_types,
            detected_patterns=detected_patterns,
            reasoning=reasoning or f"Method: {method}",
        )

    def _record_method(self, method: str):
        """Record detection method usage statistics"""
        if method not in self._stats["method_distribution"]:
            self._stats["method_distribution"][method] = 0
        self._stats["method_distribution"][method] += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics"""
        type_info = {}
        for bt, config in self.type_keywords.items():
            type_info[bt.value] = {
                "name": config["name"],
                "emoji": config["emoji"],
                "primary_count": len(config.get("primary_keywords", [])),
                "secondary_count": len(config.get("secondary_keywords", [])),
                "patterns_count": len(self.patterns.get(bt, [])),
            }

        return {
            "version": "2.2.0 (Phase 2 Enhanced)",
            "total_detections": self._stats["total_detections"],
            "method_distribution": self._stats["method_distribution"],
            "supported_types": list(type_info.keys()),
            "type_details": type_info,
            "features": [
                "Pattern matching (regex)",
                "Enhanced keyword scoring",
                "Negation detection",
                "Context awareness",
                "Synonym expansion",
                "LLM assistance (optional)",
            ],
        }


if __name__ == "__main__":
    detector = BusinessTypeDetectorV2(enable_llm=False)

    print("=" * 70)
    print("OPC-Agents Business Type Detector v2.2 (Phase 2 Enhanced)")
    print("=" * 70)

    stats = detector.get_statistics()
    print(f"\nVersion: {stats['version']}")
    print(f"Supported types: {', '.join(stats['supported_types'])}")
    print(f"Features: {', '.join(stats['features'])}")

    test_cases = [
        ("帮我规划下周的内容日历，要考虑粉丝画像", "内容创作者"),
        ("我要在Gumroad上发布一个新课程，需要定价建议", "数字产品"),
        ("帮我的淘宝店铺策划双十一促销活动", "电商运营"),
        ("客户需要一份数字化转型战略咨询提案", "咨询师"),
        ("分析一下用户在App Store上的评论反馈，生成优先级矩阵", "AI工具"),
        ("设计稿完成了，准备打包交付给客户", "创意工作者"),
        ("我的小红书账号想涨粉", "内容创作者"),
        ("这个AI应用的API响应时间太长了，需要优化", "AI工具"),
        ("我不想做电商了，想转行做内容", "内容创作者"),
        ("帮我在Figma里设计一个APP的UI原型", "创意工作者"),
    ]

    print(f"\n{'=' * 70}")
    print(f"Test Cases ({len(test_cases)})")
    print(f"{'=' * 70}")

    correct_count = 0
    for i, (input_text, expected_type) in enumerate(test_cases, 1):
        result = detector.detect(input_text)

        type_name_map = {
            "content_creator": "内容创作者",
            "digital_product": "数字产品",
            "ai_tool_builder": "AI工具开发者",
            "consultant": "专业咨询师",
            "ecommerce": "电商运营者",
            "creative_work": "创意工作者",
        }

        detected_name = type_name_map.get(
            result.business_type.value, result.business_type.value
        )
        is_correct = detected_name in expected_type
        if is_correct:
            correct_count += 1
            status = "✅"
        else:
            status = "❌"

        print(f'\n{status} [{i}] "{input_text[:45]}..."')
        print(f"   Expected: {expected_type}")
        print(f"   Detected: {result.business_type.value} ({detected_name})")
        print(f"   Confidence: {result.confidence:.3f} | Method: {result.method}")
        print(
            f"   Keywords({len(result.matched_keywords)}): {', '.join(result.matched_keywords[:4])}"
        )
        if result.detected_patterns:
            print(f"   Patterns: {len(result.detected_patterns)}")

    accuracy = (correct_count / len(test_cases)) * 100
    print(f"\n{'=' * 70}")
    print(f"Accuracy: {correct_count}/{len(test_cases)} = {accuracy:.1f}%")
    print(f"Target: 95%+ | {'✅ Met' if accuracy >= 95 else '⚠️ Needs optimization'}")
    print("=" * 70)
