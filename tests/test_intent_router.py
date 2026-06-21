import pytest
from opc_manager.intent_classifier import IntentRouter, IntentCategory


class TestIntentRouter:
    """三路路由分类测试 [S2-T6]"""

    @pytest.mark.parametrize(
        "input_text",
        [
            "你好",
            "您好",
            "hi",
            "hello",
            "嗨",
            "哈喽",
            "谢谢",
            "感谢",
            "thanks",
            "再见",
            "bye",
            "拜拜",
            "帮助",
            "help",
            "怎么用",
        ],
    )
    def test_classify_greeting(self, input_text):
        category, confidence = IntentRouter.classify_route(input_text)
        assert category == IntentCategory.GREETING
        assert confidence >= 0.9

    @pytest.mark.parametrize(
        "input_text",
        [
            "查询本月支出",
            "查看收入记录",
            "列出待办事项",
            "告诉我上周报表",
            "显示数据",
            "搜索客户信息",
            "什么是API",
            "解释一下三贤者",
        ],
    )
    def test_classify_simple(self, input_text):
        category, confidence = IntentRouter.classify_route(input_text)
        assert category == IntentCategory.SIMPLE
        assert confidence >= 0.7

    @pytest.mark.parametrize(
        "input_text",
        [
            "发邮件给张总",
            "记录一笔收入3000元",
            "生成本月经营报告",
            "删除客户记录",
            "更新发票信息",
            "执行数据导出",
            "创建新任务",
            "修改密码",
        ],
    )
    def test_classify_complex(self, input_text):
        category, confidence = IntentRouter.classify_route(input_text)
        assert category == IntentCategory.COMPLEX
        assert confidence >= 0.8

    def test_classify_default_to_complex(self):
        """不确定时默认归为复杂（保守策略）"""
        category, confidence = IntentRouter.classify_route("随机的不相关文本xyz")
        assert category == IntentCategory.COMPLEX
        assert confidence == 0.5

    def test_greeting_priority_over_complex(self):
        """问候优先于复杂动作"""
        # "帮助" 应该是 GREETING 而不是 COMPLEX
        category, _ = IntentRouter.classify_route("帮助")
        assert category == IntentCategory.GREETING

    def test_complex_priority_over_simple(self):
        """复杂动作优先于简单查询"""
        # "查询并删除" 应该是 COMPLEX（因为有"删除"）
        category, _ = IntentRouter.classify_route("查询并删除记录")
        assert category == IntentCategory.COMPLEX
