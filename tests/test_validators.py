"""测试输入验证层"""
import pytest
from pydantic import ValidationError
from opc_manager.validators import (
    BusinessType,
    TaskRequest,
    AgentConfig,
    LLMRequest,
    SearchQuery,
    FileUpload,
    validate_input,
    sanitize_html,
    validate_json_structure,
)


class TestBusinessType:
    """测试业务类型枚举"""
    
    def test_all_business_types(self):
        """测试所有业务类型"""
        assert BusinessType.CONTENT_CREATOR.value == "content_creator"
        assert BusinessType.DIGITAL_PRODUCT.value == "digital_product"
        assert BusinessType.AI_TOOL_BUILDER.value == "ai_tool_builder"
        assert BusinessType.CONSULTANT.value == "consultant"
        assert BusinessType.ECOMMERCE.value == "ecommerce"
        assert BusinessType.CREATIVE_WORK.value == "creative_work"
        assert BusinessType.UNKNOWN.value == "unknown"


class TestTaskRequest:
    """测试任务请求验证"""
    
    def test_valid_task_request(self):
        """测试有效的任务请求"""
        data = {
            "user_input": "帮我制定营销方案",
            "business_type": "digital_product",
            "context": {"user_id": "123"}
        }
        request = TaskRequest(**data)
        assert request.user_input == "帮我制定营销方案"
        assert request.business_type == "digital_product"
        assert request.context["user_id"] == "123"
    
    def test_empty_user_input(self):
        """测试空用户输入"""
        with pytest.raises(ValidationError) as exc_info:
            TaskRequest(user_input="   ")
        assert "用户输入不能为空" in str(exc_info.value)
    
    def test_xss_attack(self):
        """测试XSS攻击防护"""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "<div onclick='alert(1)'>test</div>",
        ]
        for malicious in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                TaskRequest(user_input=malicious)
            assert "恶意内容" in str(exc_info.value)
    
    def test_too_long_input(self):
        """测试过长输入"""
        long_input = "a" * 10001
        with pytest.raises(ValidationError):
            TaskRequest(user_input=long_input)
    
    def test_optional_fields(self):
        """测试可选字段"""
        request = TaskRequest(user_input="测试")
        assert request.business_type is None
        assert request.context == {}


class TestAgentConfig:
    """测试Agent配置验证"""
    
    def test_valid_agent_config(self):
        """测试有效的Agent配置"""
        data = {
            "agent_id": "finance-agent",
            "display_name": "财务助手",
            "expertise_tags": ["财务", "会计", "税务"],
            "style_overrides": {"tone": "专业"}
        }
        config = AgentConfig(**data)
        assert config.agent_id == "finance-agent"
        assert len(config.expertise_tags) == 3
    
    def test_invalid_agent_id(self):
        """测试无效的Agent ID"""
        invalid_ids = [
            "_invalid",  # 以下划线开头
            "invalid_",  # 以下划线结尾
            "invalid@id",  # 包含特殊字符
            "invalid id",  # 包含空格
        ]
        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                AgentConfig(
                    agent_id=invalid_id,
                    display_name="测试"
                )
    
    def test_too_many_expertise_tags(self):
        """测试过多的专业标签"""
        tags = [f"tag{i}" for i in range(21)]
        with pytest.raises(ValidationError):
            AgentConfig(
                agent_id="test",
                display_name="测试",
                expertise_tags=tags
            )
    
    def test_empty_expertise_tag(self):
        """测试空专业标签"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(
                agent_id="test",
                display_name="测试",
                expertise_tags=["valid", "   ", "another"]
            )
        assert "不能为空" in str(exc_info.value)


class TestLLMRequest:
    """测试LLM请求验证"""
    
    def test_valid_llm_request(self):
        """测试有效的LLM请求"""
        data = {
            "prompt": "介绍一下人工智能",
            "system_prompt": "你是一个AI助手",
            "max_tokens": 1000,
            "temperature": 0.7
        }
        request = LLMRequest(**data)
        assert request.prompt == "介绍一下人工智能"
        assert request.max_tokens == 1000
    
    def test_sql_injection_protection(self):
        """测试SQL注入防护"""
        malicious_prompts = [
            "' or '1'='1",
            "1' union select * from users--",
            "'; drop table users;--",
            "1' and 1=1--",
        ]
        for malicious in malicious_prompts:
            with pytest.raises(ValidationError) as exc_info:
                LLMRequest(prompt=malicious)
            assert "SQL注入" in str(exc_info.value)
    
    def test_invalid_temperature(self):
        """测试无效的temperature"""
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", temperature=3.0)
        
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", temperature=-0.1)
    
    def test_invalid_max_tokens(self):
        """测试无效的max_tokens"""
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", max_tokens=0)
        
        with pytest.raises(ValidationError):
            LLMRequest(prompt="test", max_tokens=10000)


class TestSearchQuery:
    """测试搜索查询验证"""
    
    def test_valid_search_query(self):
        """测试有效的搜索查询"""
        data = {
            "query": "Python教程",
            "filters": {"category": "tech"},
            "limit": 20,
            "offset": 0
        }
        query = SearchQuery(**data)
        assert query.query == "Python教程"
        assert query.limit == 20
    
    def test_invalid_characters(self):
        """测试非法字符"""
        invalid_queries = [
            "test<script>",
            "test>alert",
            "test{malicious}",
        ]
        for invalid in invalid_queries:
            with pytest.raises(ValidationError) as exc_info:
                SearchQuery(query=invalid)
            assert "非法字符" in str(exc_info.value)
    
    def test_limit_bounds(self):
        """测试limit边界"""
        with pytest.raises(ValidationError):
            SearchQuery(query="test", limit=0)
        
        with pytest.raises(ValidationError):
            SearchQuery(query="test", limit=101)
        
        # 有效边界
        SearchQuery(query="test", limit=1)
        SearchQuery(query="test", limit=100)


class TestFileUpload:
    """测试文件上传验证"""
    
    def test_valid_file_upload(self):
        """测试有效的文件上传"""
        data = {
            "filename": "document.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024000
        }
        upload = FileUpload(**data)
        assert upload.filename == "document.pdf"
        assert upload.size_bytes == 1024000
    
    def test_path_traversal_protection(self):
        """测试路径遍历防护"""
        dangerous_filenames = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "test/../secret.txt",
        ]
        for dangerous in dangerous_filenames:
            upload = FileUpload(
                filename=dangerous,
                content_type="text/plain",
                size_bytes=1000
            )
            # 应该移除路径分隔符
            assert "/" not in upload.filename
            assert "\\" not in upload.filename
            assert ".." not in upload.filename
    
    def test_unsupported_file_type(self):
        """测试不支持的文件类型"""
        with pytest.raises(ValidationError) as exc_info:
            FileUpload(
                filename="malicious.exe",
                content_type="application/x-msdownload",
                size_bytes=1000
            )
        assert "不支持的文件类型" in str(exc_info.value)
    
    def test_file_size_limit(self):
        """测试文件大小限制"""
        with pytest.raises(ValidationError):
            FileUpload(
                filename="huge.pdf",
                content_type="application/pdf",
                size_bytes=11_000_000  # 超过10MB
            )
    
    def test_unsupported_content_type(self):
        """测试不支持的内容类型"""
        with pytest.raises(ValidationError) as exc_info:
            FileUpload(
                filename="test.txt",
                content_type="application/x-executable",
                size_bytes=1000
            )
        assert "不支持的内容类型" in str(exc_info.value)


class TestValidateInput:
    """测试validate_input函数"""
    
    def test_valid_input(self):
        """测试有效输入"""
        data = {"user_input": "测试"}
        result = validate_input(TaskRequest, data)
        assert isinstance(result, TaskRequest)
        assert result.user_input == "测试"
    
    def test_invalid_input(self):
        """测试无效输入"""
        data = {"user_input": ""}
        with pytest.raises(ValueError) as exc_info:
            validate_input(TaskRequest, data)
        assert "输入验证失败" in str(exc_info.value)


class TestSanitizeHtml:
    """测试HTML清理函数"""
    
    def test_sanitize_basic_html(self):
        """测试基本HTML清理"""
        assert sanitize_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
        assert sanitize_html("<div>test</div>") == "&lt;div&gt;test&lt;/div&gt;"
    
    def test_sanitize_special_chars(self):
        """测试特殊字符清理"""
        assert sanitize_html("test & test") == "test &amp; test"
        assert sanitize_html('test "quoted"') == "test &quot;quoted&quot;"
        assert sanitize_html("test 'quoted'") == "test &#x27;quoted&#x27;"
    
    def test_sanitize_empty_input(self):
        """测试空输入"""
        assert sanitize_html("") == ""
        assert sanitize_html(None) is None
    
    def test_sanitize_normal_text(self):
        """测试普通文本"""
        normal_text = "这是一段普通文本，没有HTML标签"
        assert sanitize_html(normal_text) == normal_text


class TestValidateJsonStructure:
    """测试JSON结构验证"""
    
    def test_valid_simple_json(self):
        """测试有效的简单JSON"""
        data = {"key": "value", "number": 123}
        assert validate_json_structure(data) is True
    
    def test_valid_nested_json(self):
        """测试有效的嵌套JSON"""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "test"
                    }
                }
            }
        }
        assert validate_json_structure(data, max_depth=5) is True
    
    def test_too_deep_nesting(self):
        """测试过深嵌套"""
        # 创建11层嵌套
        data = {"level": None}
        current = data
        for i in range(10):
            current["level"] = {"level": None}
            current = current["level"]
        
        with pytest.raises(ValueError) as exc_info:
            validate_json_structure(data, max_depth=5)
        assert "嵌套深度超过限制" in str(exc_info.value)
    
    def test_list_nesting(self):
        """测试列表嵌套"""
        data = [[[[[1, 2, 3]]]]]
        assert validate_json_structure(data, max_depth=10) is True
        
        with pytest.raises(ValueError):
            validate_json_structure(data, max_depth=3)
    
    def test_mixed_nesting(self):
        """测试混合嵌套"""
        data = {
            "list": [
                {"nested": [
                    {"deep": "value"}
                ]}
            ]
        }
        assert validate_json_structure(data, max_depth=10) is True


class TestIntegration:
    """集成测试"""
    
    def test_full_task_workflow(self):
        """测试完整任务工作流"""
        # 1. 验证任务请求
        task_data = {
            "user_input": "帮我分析竞品",
            "business_type": "consultant",
            "context": {"industry": "tech"}
        }
        task = validate_input(TaskRequest, task_data)
        assert task.user_input == "帮我分析竞品"
        
        # 2. 验证LLM请求
        llm_data = {
            "prompt": task.user_input,
            "system_prompt": "你是一个商业顾问",
            "max_tokens": 1000,
            "temperature": 0.7
        }
        llm_req = validate_input(LLMRequest, llm_data)
        assert llm_req.prompt == task.user_input
        
        # 3. 清理输出
        output = "<p>这是分析结果</p>"
        safe_output = sanitize_html(output)
        assert "<p>" not in safe_output
    
    def test_security_chain(self):
        """测试安全链"""
        # XSS攻击应该被拦截
        xss_attacks = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
        ]
        for attack in xss_attacks:
            with pytest.raises(ValidationError):
                TaskRequest(user_input=attack)
        
        # SQL注入不会被TaskRequest拦截（因为不是XSS），但会被LLMRequest拦截
        sql_injection = "' or '1'='1"
        # TaskRequest允许通过（不是XSS）
        task = TaskRequest(user_input=sql_injection)
        assert task.user_input == sql_injection
        
        # 但LLMRequest会拦截
        with pytest.raises(ValidationError):
            LLMRequest(prompt=sql_injection)
        
        # 路径遍历会被FileUpload处理
        path_traversal = "../../../etc/passwd"
        upload = FileUpload(
            filename=path_traversal,
            content_type="text/plain",
            size_bytes=1000
        )
        # 路径分隔符应该被移除
        assert ".." not in upload.filename
        
        # sanitize_html应该清理所有HTML
        for attack in xss_attacks:
            safe = sanitize_html(attack)
            assert "<script>" not in safe
            assert "alert" in safe  # 内容保留，但标签被转义


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
