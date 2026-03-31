#!/usr/bin/env python3

import time
import re
import json
from typing import Dict, List, Any, Optional


class ThreeSagesManager:

    def __init__(self):
        pass

    SAGE_INFO = {
        "astra": {
            "name": "阿斯特拉",
            "title": "战略贤者",
            "focus": "长期战略规划、市场趋势分析、竞争格局评估"
        },
        "terra": {
            "name": "泰拉",
            "title": "执行贤者",
            "focus": "资源优化、执行效率、风险管理"
        },
        "nova": {
            "name": "诺娃",
            "title": "创新贤者",
            "focus": "技术创新、商业模式、颠覆性思维"
        }
    }

    def start_three_sages_decision(self, issue: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        print(f"[三贤者] 启动决策过程: {issue[:50]}...")

        sage_opinions = {}
        for sage_id in ["astra", "terra", "nova"]:
            info = self.SAGE_INFO[sage_id]
            prompt = (
                f"你是{info['name']}，{info['title']}，专长于{info['focus']}。\n"
                f"请针对以下任务进行评估，严格按JSON格式输出，不要输出其他内容：\n"
                f"{{\n"
                f"  \"internal_resources\": \"内部资源评估：有哪些本地Agent/部门可以完成？缺少什么能力？\",\n"
                f"  \"external_relations\": \"外部关系评估：是否需要外部资源/合作/搜索？风险是什么？\",\n"
                f"  \"risk_assessment\": \"风险评估：技术风险、时间风险、资源风险\",\n"
                f"  \"strategy\": \"从{info['focus']}角度的战略建议\",\n"
                f"  \"action_items\": [\"具体行动1\", \"具体行动2\", \"具体行动3\"]\n"
                f"}}\n\n"
                f"任务：{issue}"
            )
            opinion = self.call_llm_api(prompt, model_name="glm")
            structured = self._parse_structured_opinion(opinion, info['title'])
            sage_opinions[sage_id] = structured

        for sage_id, opinion in sage_opinions.items():
            info = self.SAGE_INFO[sage_id]
            print(f"[三贤者] {info['name']}: 资源={opinion.get('internal_resources','')[:30]}...")

        print("[三贤者] 开始共识综合...")
        synthesis = self._generate_synthesis(issue, sage_opinions)

        decision_result = {
            "issue": issue,
            "sages": [{
                "id": sage_id,
                "name": self.SAGE_INFO[sage_id]["name"],
                "title": self.SAGE_INFO[sage_id]["title"],
                "opinion": opinion
            } for sage_id, opinion in sage_opinions.items()],
            "synthesis": synthesis,
            "timestamp": time.time(),
            "context": context
        }

        print(f"[三贤者] 决策完成，综合建议: {synthesis.get('summary','')[:80]}...")
        return decision_result

    def _parse_structured_opinion(self, raw_opinion: str, sage_title: str) -> Dict[str, Any]:
        try:
            json_match = re.search(r'\{[\s\S]*\}', raw_opinion)
            if json_match:
                parsed = json.loads(json_match.group())
                required_keys = ["internal_resources", "external_relations", "risk_assessment", "strategy", "action_items"]
                if all(k in parsed for k in required_keys):
                    return parsed
        except (json.JSONDecodeError, Exception):
            pass

        print(f"[三贤者] {sage_title} JSON解析失败，使用文本提取")
        return {
            "internal_resources": self._extract_section(raw_opinion, ["内部资源", "internal_resources", "本地Agent"]),
            "external_relations": self._extract_section(raw_opinion, ["外部关系", "external_relations", "外部资源", "合作"]),
            "risk_assessment": self._extract_section(raw_opinion, ["风险评估", "risk_assessment", "风险"]),
            "strategy": raw_opinion[-200:] if len(raw_opinion) > 200 else raw_opinion,
            "action_items": re.findall(r'[\d]+[.、]\s*(.+)', raw_opinion)[:5]
        }

    def _extract_section(self, text: str, keywords: List[str]) -> str:
        for kw in keywords:
            idx = text.find(kw)
            if idx >= 0:
                end = len(text)
                for end_kw in ["\n\n", "风险", "战略", "执行", "创新", "action_items", "strategy"]:
                    end_idx = text.find(end_kw, idx + len(kw))
                    if end_idx > idx and end_idx < end:
                        end = end_idx
                section = text[idx:end].strip()
                if len(section) > 200:
                    section = section[:200] + "..."
                return section
        return "未明确评估"

    def _generate_synthesis(self, issue: str, sage_opinions: Dict[str, str]) -> Dict[str, Any]:
        try:
            opinions_text = ""
            for sage_id, opinion in sage_opinions.items():
                info = self.SAGE_INFO[sage_id]
                opinions_text += (
                    f"\n### {info['name']}（{info['title']}）\n"
                    f"- 内部资源：{opinion.get('internal_resources', '')}\n"
                    f"- 外部关系：{opinion.get('external_relations', '')}\n"
                    f"- 风险评估：{opinion.get('risk_assessment', '')}\n"
                    f"- 战略建议：{opinion.get('strategy', '')}\n"
                    f"- 行动项：{', '.join(opinion.get('action_items', []))}\n"
                )

            prompt = (
                f"基于三位贤者的评估，为以下任务生成执行计划建议：\n"
                f"任务：{issue}\n"
                f"{opinions_text}\n\n"
                f"请严格按JSON格式输出：\n"
                f"{{\n"
                f"  \"summary\": \"一句话总结\",\n"
                f"  \"execution_steps\": [\n"
                f"    {{\"step\": 1, \"task\": \"任务名\", \"department\": \"部门名\", \"description\": \"具体描述\", \"deliverable\": \"预期产出物\", \"depends_on\": [依赖的步骤编号], \"required_skills\": [\"技能1\"], \"acceptance_criteria\": [\"验收标准1\"]}}\n"
                f"  ],\n"
                f"  \"monitoring_plan\": [\n"
                f"    {{\"checkpoint\": \"检查点描述\", \"trigger\": \"触发条件\"}}\n"
                f"  ],\n"
                f"  \"risk_mitigation\": [\"风险缓解措施1\", \"风险缓解措施2\"]\n"
                f"}}\n\n"
                f"只输出JSON，不要其他内容。"
            )

            response = self.call_llm_api(prompt, model_name="glm")
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                synthesis = json.loads(json_match.group())
                synthesis["raw_text"] = response
                return synthesis
            else:
                return {
                    "summary": response[:200] if response else "综合评估完成",
                    "execution_steps": [],
                    "monitoring_plan": [],
                    "risk_mitigation": [],
                    "raw_text": response
                }
        except Exception as e:
            print(f"[三贤者] 共识综合失败: {e}")
            return {
                "summary": f"综合评估完成（生成失败: {e}）",
                "execution_steps": [],
                "monitoring_plan": [],
                "risk_mitigation": [],
                "raw_text": ""
            }

    def call_llm_api(self, prompt: str, model_name: str = "glm") -> Optional[str]:
        try:
            from model_integration.model_manager import ModelManager
            model_manager = ModelManager()
            return model_manager.generate_response(prompt, model=model_name)
        except Exception as e:
            print(f"[三贤者] 调用大模型失败: {e}")
            raise
