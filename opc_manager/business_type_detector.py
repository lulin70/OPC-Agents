"""
业务类型检测器 - BusinessTypeDetector

基于关键词匹配和上下文推理，识别用户所属的6大业务类型
Phase 1 MVP版本：主要使用关键词匹配
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from opc_manager.business_types import BusinessType


@dataclass
class DetectionResult:
    """检测结果"""
    business_type: BusinessType
    confidence: float
    method: str  # "keyword_match", "profile_inference", "history_analysis", "default"
    matched_keywords: List[str]
    alternative_types: List[Tuple[BusinessType, float]]  # 备选类型及置信度


class BusinessTypeDetector:
    """
    业务类型检测器

    策略：
    1. 关键词匹配（主策略）- 从用户输入中提取特征词
    2. 用户档案推断（辅助）- 如果用户有已保存的类型偏好
    3. 历史对话分析（辅助）- 分析历史对话中的模式
    4. 默认兜底 - 如果以上都失败，返回默认类型
    """

    def __init__(self):
        """初始化检测器，加载各类型的关键词库"""
        self.type_keywords = self._init_keyword_database()
        self.default_type = BusinessType.CONTENT_CREATOR
        self.confidence_threshold = 0.15

    def _init_keyword_database(self) -> Dict[BusinessType, Dict[str, Any]]:
        """
        初始化各业务类型的关键词数据库

        每个类型包含：
        - primary_keywords: 强指示词（权重高）
        - secondary_keywords: 弱指示词（权重中）
        - context_phrases: 上下文短语（用于增强判断）
        - negative_keywords: 排除词（降低该类型的可能性）
        """
        return {
            BusinessType.CONTENT_CREATOR: {
                "name": "内容创作者",
                "emoji": "✍️",
                "primary_keywords": [
                    "内容", "创作", "写作", "文章", "博客", "公众号",
                    "小红书", "抖音", "视频", "直播", "UP主", "博主",
                    "粉丝", "涨粉", "爆款", "选题", "日历", "排期",
                    "种草", "完播率", "互动率", "阅读量", "10万+",
                    "流量", "变现", "广告", "品牌合作", "MCN"
                ],
                "secondary_keywords": [
                    "发布", "更新", "推送", "素材", "文案",
                    "标题", "封面", "脚本", "拍摄", "剪辑",
                    "平台", "算法", "推荐", "热搜", "话题"
                ],
                "context_phrases": [
                    "帮我写一篇", "下周发什么", "内容规划",
                    "粉丝画像", "多平台", "矩阵运营"
                ],
                "weight": 1.5  # 该类型的基准权重
            },

            BusinessType.DIGITAL_PRODUCT: {
                "name": "数字产品开发者",
                "emoji": "💰",
                "primary_keywords": [
                    "数字产品", "知识付费", "课程", "电子书", "模板",
                    "小报童", "Gumroad", "Teachable", "产品上架",
                    "定价", "销售页", "landing page", "漏斗",
                    "付费用户", "订阅", "会员", "社群", "知识星球",
                    "专栏", "训练营", "SaaS", "工具", "插件"
                ],
                "secondary_keywords": [
                    "售卖", "收入", "营收", "转化率", "客单价",
                    "复购", "续费", "退款", "评价", "评分",
                    "产品包装", "USP", "卖点", "价值主张"
                ],
                "context_phrases": [
                    "我要卖", "如何定价", "写销售页",
                    "产品发布", "上线", "推广课程"
                ],
                "weight": 1.3
            },

            BusinessType.AI_TOOL_BUILDER: {
                "name": "AI工具开发者",
                "emoji": "🤖",
                "primary_keywords": [
                    "AI工具", "人工智能", "API", "GPT", "LLM",
                    "ChatGPT", "Claude", "模型", "训练", "微调",
                    "应用", "插件", "扩展", "Agent", "智能助手",
                    "自动化", "代码", "开源", "GitHub", "部署",
                    "用户反馈", "评论", "Issues", "PR", "版本",
                    "功能", "迭代", "路线图", "roadmap"
                ],
                "secondary_keywords": [
                    "技术文档", "SDK", "集成", "接口", "Token",
                    "调用", "延迟", "性能", "优化", "Bug",
                    "Feature Request", "Changelog", "Release"
                ],
                "context_phrases": [
                    "我的工具", "用户说", "App Store评论",
                    "GitHub Issues", "新功能", "版本更新"
                ],
                "weight": 1.4
            },

            BusinessType.CONSULTANT: {
                "name": "专业咨询师",
                "emoji": "💼",
                "primary_keywords": [
                    "咨询", "顾问", "提案", "建议书", "方案",
                    "客户", "项目", "服务", "专业", "专家",
                    "战略", "规划", "分析", "研究", "报告",
                    "演示", "汇报", "PPT", "交付物", "合同",
                    "报价", "费用", "时薪", "按项目", "retainer"
                ],
                "secondary_keywords": [
                    "行业", "市场", "竞争", "痛点", "需求",
                    "解决方案", "方法论", "框架", "最佳实践",
                    "案例", "经验", "洞察", "建议"
                ],
                "context_phrases": [
                    "我的客户", "给客户写", "咨询项目",
                    "服务报价", "专业建议"
                ],
                "weight": 1.2
            },

            BusinessType.ECOMMERCE: {
                "name": "电商运营者",
                "emoji": "🛒",
                "primary_keywords": [
                    "电商", "淘宝", "天猫", "京东", "拼多多",
                    "店铺", "商品", "SKU", "库存", "订单",
                    "发货", "物流", "快递", "GMV", "销售额",
                    "转化率", "客单价", "访客", "UV", "PV",
                    "直通车", "钻展", "促销", "活动", "双十一",
                    "618", "直播带货", "供应链", "选品"
                ],
                "secondary_keywords": [
                    "详情页", "主图", "标题优化", "SEO",
                    "评价", "DSR", "退款", "售后",
                    "客服", "旺信", "聚划算", "秒杀"
                ],
                "context_phrases": [
                    "我的店铺", "商品上架", "活动报名",
                    "库存预警", "订单处理"
                ],
                "weight": 1.3
            },

            BusinessType.CREATIVE_WORK: {
                "name": "创意工作者",
                "emoji": "🎨",
                "primary_keywords": [
                    "设计", "创意", "作品", "交付", "客户",
                    "UI", "UX", "平面", "品牌", "logo",
                    "插画", "摄影", "视频制作", "剪辑",
                    "作品集", "portfolio", "提案", "样机",
                    "Figma", "Sketch", "Photoshop", "AI绘画",
                    "Midjourney", "Stable Diffusion", "DALL-E"
                ],
                "secondary_keywords": [
                    "视觉", "配色", "排版", "字体", "图标",
                    "原型", "交互", "动效", "渲染",
                    "素材", "版权", "商用", "授权"
                ],
                "context_phrases": [
                    "设计稿", "效果图", "客户反馈",
                    "作品集整理", "创意方案"
                ],
                "weight": 1.2
            }
        }

    def detect(
        self,
        input_text: str,
        user_profile: Optional[Dict] = None,
        history: Optional[List[Dict]] = None,
        min_confidence: float = None
    ) -> DetectionResult:
        """
        检测用户的业务类型

        Args:
            input_text: 用户输入文本
            user_profile: 用户档案信息（可选）
            history: 对话历史（可选）
            min_confidence: 最小置信度阈值（可选）

        Returns:
            DetectionResult: 包含检测到的类型、置信度、方法等信息
        """
        if min_confidence is None:
            min_confidence = self.confidence_threshold

        scores = {}

        for business_type, keyword_config in self.type_keywords.items():
            score = self._calculate_type_score(
                input_text=input_text,
                keyword_config=keyword_config
            )
            scores[business_type] = score

        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        best_type, best_score = sorted_types[0]

        if best_score < min_confidence and user_profile:
            profile_type = self._infer_from_profile(user_profile)
            if profile_type:
                best_type = profile_type
                best_score = 0.6
                method = "profile_inference"
            else:
                best_type = self.default_type
                best_score = 0.2
                method = "default"
        elif best_score >= min_confidence:
            method = "keyword_match"
        else:
            best_type = self.default_type
            best_score = 0.2
            method = "default"

        matched_keywords = self._extract_matched_keywords(
            input_text,
            self.type_keywords[best_type]
        )

        alternative_types = [
            (bt, score) for bt, score in sorted_types[1:4]
            if score > 0.1
        ]

        return DetectionResult(
            business_type=best_type,
            confidence=best_score,
            method=method,
            matched_keywords=matched_keywords,
            alternative_types=alternative_types
        )

    def _calculate_type_score(self, input_text: str, keyword_config: Dict) -> float:
        """
        计算某业务类型的匹配置信度

        算法：
        - primary_keywords 命中：每个 +2分
        - secondary_keywords 命中：每个 +1分
        - context_phrases 命中：每个 +3分
        - 总分归一化到 0-1 范围
        - 乘以该类型的 weight 系数
        """
        text_lower = input_text.lower()

        primary_matches = sum(
            1 for kw in keyword_config["primary_keywords"]
            if kw.lower() in text_lower
        )

        secondary_matches = sum(
            1 for kw in keyword_config["secondary_keywords"]
            if kw.lower() in text_lower
        )

        context_matches = sum(
            1 for phrase in keyword_config["context_phrases"]
            if phrase.lower() in text_lower
        )

        raw_score = (
            primary_matches * 2.0 +
            secondary_matches * 1.0 +
            context_matches * 3.0
        )

        max_possible_score = (
            len(keyword_config["primary_keywords"]) * 2.0 +
            len(keyword_config["context_phrases"]) * 3.0
        ) * 0.3  # 不期望所有关键词都命中，30%命中率已经很高

        normalized_score = min(raw_score / max(max_possible_score, 1), 1.0)
        weighted_score = normalized_score * keyword_config.get("weight", 1.0)

        return round(weighted_score, 3)

    def _extract_matched_keywords(self, input_text: str, keyword_config: Dict) -> List[str]:
        """提取命中的关键词"""
        text_lower = input_text.lower()
        matched = []

        all_keywords = (
            keyword_config.get("primary_keywords", []) +
            keyword_config.get("secondary_keywords", []) +
            keyword_config.get("context_phrases", [])
        )

        for kw in all_keywords:
            if kw.lower() in text_lower:
                matched.append(kw)

        return matched[:10]  # 最多返回10个

    def _infer_from_profile(self, user_profile: Dict) -> Optional[BusinessType]:
        """从用户档案推断业务类型"""
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

    def analyze_history(self, history: List[Dict]) -> Optional[BusinessType]:
        """分析历史对话，推断主导的业务类型"""
        if not history or len(history) < 3:
            return None

        type_counts = {}
        for item in history[-10:]:
            user_message = item.get("user", "") or item.get("input", "") or item.get("message", "")
            if user_message:
                result = self.detect(user_message)
                bt_key = result.business_type.value
                if bt_key not in type_counts:
                    type_counts[bt_key] = {"count": 0, "total_confidence": 0.0}
                type_counts[bt_key]["count"] += 1
                type_counts[bt_key]["total_confidence"] += result.confidence

        if not type_counts:
            return None

        dominant_type = max(
            type_counts.items(),
            key=lambda x: (x[1]["count"], x[1]["total_confidence"])
        )

        if dominant_type[1]["count"] >= 3:
            return BusinessType.from_string(dominant_type[0])

        return None

    def get_type_info(self, business_type: BusinessType) -> Dict[str, Any]:
        """获取业务类型的详细信息"""
        config = self.type_keywords.get(business_type)
        if not config:
            return {}

        return {
            "type": business_type.value,
            "name": config["name"],
            "emoji": config["emoji"],
            "primary_keywords_count": len(config.get("primary_keywords", [])),
            "secondary_keywords_count": len(config.get("secondary_keywords", [])),
            "weight": config.get("weight", 1.0)
        }


if __name__ == "__main__":
    detector = BusinessTypeDetector()

    print("=" * 60)
    print("OPC-Agents 业务类型检测器 v1.0")
    print("=" * 60)

    test_cases = [
        ("帮我规划下周的内容日历，要考虑粉丝画像", "内容创作者"),
        ("我要发布一个新的AI工具到Product Hunt", "AI工具开发者"),
        ("帮我的淘宝店铺做个双十一活动策划", "电商运营者"),
        ("客户需要一份战略咨询提案", "专业咨询师"),
        ("我在Gumroad上有个新的课程要上架", "数字产品开发者"),
        ("设计稿完成了，准备给客户交付", "创意工作者"),
        ("明天下午组织个产品评审会议", "通用/默认"),
        ("帮我写一份月度工作报告", "咨询师/内容创作者"),
        ("分析一下用户在App Store上的评论反馈", "AI工具开发者"),
        ("我的小红书账号想涨粉，有什么建议？", "内容创作者"),
    ]

    print(f"\n🧪 测试用例 ({len(test_cases)} 个)\n")

    correct_count = 0
    for i, (input_text, expected_type) in enumerate(test_cases, 1):
        result = detector.detect(input_text)

        type_name_map = {
            "content_creator": "内容创作者",
            "digital_product": "数字产品开发者",
            "ai_tool_builder": "AI工具开发者",
            "consultant": "专业咨询师",
            "ecommerce": "电商运营者",
            "creative_work": "创意工作者"
        }
        detected_name = type_name_map.get(result.business_type.value, result.business_type.value)
        is_correct = detected_name in expected_type
        if is_correct:
            correct_count += 1
            status = "✅"
        else:
            status = "❌"

        print(f"{status} 测试{i}: \"{input_text[:40]}...\"")
        print(f"   预期类型: {expected_type}")
        type_info = detector.get_type_info(result.business_type)
        print(f"   检测结果: {result.business_type.value} ({type_info.get('name', 'Unknown')})")
        print(f"   置信度: {result.confidence:.3f} | 方法: {result.method}")
        print(f"   命中关键词: {', '.join(result.matched_keywords[:5])}")
        if result.alternative_types:
            alt_str = ", ".join([f"{bt.value}({score:.2f})" for bt, score in result.alternative_types])
            print(f"   备选类型: {alt_str}")
        print()

    accuracy = (correct_count / len(test_cases)) * 100
    print("=" * 60)
    print(f"📊 准确率: {correct_count}/{len(test_cases)} = {accuracy:.1f}%")
    print("=" * 60)
