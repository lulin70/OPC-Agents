#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.three_sages import ThreeSagesManager
from opc_manager.core import OPCManager

print("=== ThreeSages Unit Tests ===")
ts = ThreeSagesManager()

json_input = '{"internal_resources": "3 agents", "external_relations": "none", "risk_assessment": "low", "strategy": "execute", "action_items": ["step1", "step2"]}'
r = ts._parse_structured_opinion(json_input, 'T')
assert r['internal_resources'] == '3 agents', f"Got: {r['internal_resources']}"
assert r['strategy'] == 'execute'
assert len(r['action_items']) == 2
print("  PASS _parse_structured_opinion (JSON)")

text_input = "内部资源评估：本地有design部门。外部关系：无需外部。风险评估：低。战略建议：直接执行。1. 设计 2. 开发"
r = ts._parse_structured_opinion(text_input, 'T')
assert '内部资源' in r['internal_resources']
assert len(r['action_items']) >= 1
print("  PASS _parse_structured_opinion (text fallback)")

text = "## 内部资源评估\n本地有3个Agent\n\n## 风险评估\n低风险"
r = ts._extract_section(text, ['内部资源评估'])
assert '3个Agent' in r
print("  PASS _extract_section")

assert len(ts.SAGE_INFO) == 3
print("  PASS SAGE_INFO structure")

print("\n=== OPCManager Tests ===")
mgr = OPCManager()

r = mgr.decompose_task("test task")
assert 'execution_steps' in r
print("  PASS decompose_task (no synthesis)")

r = mgr.generate_plan_markdown("test", {"summary": "test", "sages": []}, [], [], "t-1")
assert "test" in r
assert "t-1" in r
print("  PASS generate_plan_markdown")

print("\n=== Security Tests ===")
from opc_hr.mcp_integration import MCPIntegration
mcp = MCPIntegration()

trusted = mcp._load_trusted_sources()
assert "microsoft/autogen" in trusted
print("  PASS _load_trusted_sources")

r = mcp._scan_code_safety("nonexistent/repo123")
assert r['risk_level'] in ['low', 'unknown']
print("  PASS _scan_code_safety (nonexistent)")

agent_data = {"name": "t", "repo_full_name": "microsoft/autogen", "stars": 100, "forks": 50, "license": "MIT", "description": "t", "language": "Python"}
r = mcp._verify_resource(agent_data, "agent")
assert r['trusted'] == True
assert r['security_score'] == 1.0
print("  PASS _verify_resource (trusted)")

agent_data2 = {"name": "t", "repo_full_name": "unknown/repo", "stars": 0, "forks": 0, "description": "", "language": ""}
r = mcp._verify_resource(agent_data2, "agent")
assert r['trusted'] == False
assert r['verified'] == False
print("  PASS _verify_resource (untrusted)")

print("\n=== ALL TESTS PASSED ===")
