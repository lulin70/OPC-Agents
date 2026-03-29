#!/usr/bin/env python3
"""
Three Sages decision system for OPC Manager
"""

import time
from typing import Dict, List, Any, Optional

class ThreeSagesManager:
    """Three Sages manager for OPC-Agents system"""
    
    def __init__(self):
        """Initialize the Three Sages Manager"""
        pass
    
    def start_three_sages_decision(self, issue: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Start three sages decision process
        
        Args:
            issue: The issue to decide
            context: Additional context information
            
        Returns:
            Decision result
        """
        print(f"[三贤者] 启动决策过程: {issue}")
        
        # 增强的三贤者决策系统 - 高维生物设定
        sages = ["astra", "terra", "nova"]
        
        # 三贤者详细设定
        sage_info = {
            "astra": {
                "name": "阿斯特拉",
                "title": "战略贤者",
                "origin": "高维空间",
                "ability": "预见未来趋势，掌握宏观战略",
                "personality": "冷静、理性、远见卓识",
                "focus": "长期战略规划、市场趋势分析、竞争格局评估"
            },
            "terra": {
                "name": "泰拉",
                "title": "执行贤者",
                "origin": "高维空间",
                "ability": "优化资源配置，确保高效执行",
                "personality": "务实、严谨、注重细节",
                "focus": "资源优化、执行效率、风险管理"
            },
            "nova": {
                "name": "诺娃",
                "title": "创新贤者",
                "origin": "高维空间",
                "ability": "突破思维局限，创造全新可能性",
                "personality": "激进、创意、勇于探索",
                "focus": "技术创新、商业模式、颠覆性思维"
            }
        }
        
        # 使用大模型获取三贤者的真实意见
        sage_opinions = {}
        for sage in sages:
            info = sage_info[sage]
            prompt = f"你是{info['name']}，{info['title']}，来自{info['origin']}。你的能力是{info['ability']}，性格{info['personality']}，专长于{info['focus']}。请针对以下问题提供专业的分析和建议：{issue}"
            
            # 调用大模型获取真实意见
            opinion = self.call_llm_api(prompt, model_name="glm")
            if opinion:
                sage_opinions[sage] = opinion
            else:
                # 备用意见
                sage_opinions[sage] = f"作为{info['title']}，我分析了 {issue}。建议考虑：1. 从{info['focus'].split('、')[0]}角度分析 2. 制定详细的行动计划 3. 评估潜在风险 4. 优化资源配置。"
        
        # 显示三贤者信息和意见
        for sage in sages:
            info = sage_info[sage]
            print(f"[三贤者] {info['name']} ({info['title']})")
            print(f"  来源: {info['origin']}")
            print(f"  能力: {info['ability']}")
            print(f"  性格: {info['personality']}")
            print(f"  专长: {info['focus']}")
            print(f"  意见: {sage_opinions[sage]}")
            print()
        
        # 高维生物的共识决策过程
        print("[三贤者] 开始高维共识过程...")
        print("[三贤者] 连接高维意识，共享知识与智慧...")
        print("[三贤者] 融合不同视角，形成全面认知...")
        
        # 基于共识的决策
        # 高维生物会基于整体利益做出最佳决策，而不是简单的投票
        decision_factors = {
            "战略价值": 0.4,  # 阿斯特拉的权重
            "执行可行性": 0.3,  # 泰拉的权重
            "创新潜力": 0.3   # 诺娃的权重
        }
        
        # 分析三贤者意见并生成评分
        scores = {
            "战略价值": self._analyze_sage_opinion(sage_opinions["astra"], "战略价值"),
            "执行可行性": self._analyze_sage_opinion(sage_opinions["terra"], "执行可行性"),
            "创新潜力": self._analyze_sage_opinion(sage_opinions["nova"], "创新潜力")
        }
        
        # 计算综合得分
        total_score = sum(scores[factor] * weight for factor, weight in decision_factors.items())
        decision = total_score >= 0.8  # 阈值为0.8
        
        # 生成最终决策建议
        decision_advice = self._generate_decision_advice(issue, decision, scores, sage_opinions)
        
        decision_result = {
            "issue": issue,
            "sages": [{
                "id": sage,
                "name": sage_info[sage]["name"],
                "title": sage_info[sage]["title"],
                "opinion": sage_opinions[sage]
            } for sage in sages],
            "decision_factors": decision_factors,
            "scores": scores,
            "total_score": total_score,
            "decision": "通过" if decision else "否决",
            "advice": decision_advice,
            "timestamp": time.time(),
            "context": context
        }
        
        print(f"[三贤者] 决策结果: {decision_result['decision']} (综合得分: {total_score:.2f}/1.0)")
        print(f"[三贤者] 决策依据: 战略价值({scores['战略价值']:.2f}) × 0.4 + 执行可行性({scores['执行可行性']:.2f}) × 0.3 + 创新潜力({scores['创新潜力']:.2f}) × 0.3")
        print(f"[三贤者] 决策建议: {decision_advice[:100]}...")
        
        return decision_result
    
    def _analyze_sage_opinion(self, opinion: str, factor: str) -> float:
        """分析贤者意见并给出评分
        
        Args:
            opinion: 贤者的意见
            factor: 评估因素
            
        Returns:
            评分 (0-1)
        """
        try:
            from zeroclaw_integration import ZeroClawIntegration
            zero_claw = ZeroClawIntegration()
            
            # 构建评分请求
            prompt = f"请对以下贤者意见在'{factor}'方面进行评分（0-1之间的小数），并简要说明理由：\n意见：{opinion}\n\n评分："
            
            # 调用大模型获取评分
            response = zero_claw.call_llm(prompt, model="glm")
            
            # 解析评分
            import re
            score_match = re.search(r'\d+\.\d+', response)
            if score_match:
                score = float(score_match.group())
                # 确保评分在0-1之间
                return min(1.0, max(0.0, score))
            else:
                # 如果解析失败，使用基于关键词的评分
                if factor == "战略价值":
                    strategic_keywords = ["战略", "趋势", "长期", "竞争", "定位", "规划"]
                    score = 0.7 + 0.3 * sum(1 for keyword in strategic_keywords if keyword in opinion)
                elif factor == "执行可行性":
                    execution_keywords = ["执行", "资源", "时间", "风险", "指标", "计划"]
                    score = 0.6 + 0.4 * sum(1 for keyword in execution_keywords if keyword in opinion)
                else:  # 创新潜力
                    innovation_keywords = ["创新", "技术", "模式", "机会", "突破", "差异化"]
                    score = 0.65 + 0.35 * sum(1 for keyword in innovation_keywords if keyword in opinion)
                return min(1.0, max(0.5, score))
        except Exception as e:
            print(f"[三贤者] 分析贤者意见失败: {e}")
            # 失败时使用基于关键词的评分
            if factor == "战略价值":
                strategic_keywords = ["战略", "趋势", "长期", "竞争", "定位", "规划"]
                score = 0.7 + 0.3 * sum(1 for keyword in strategic_keywords if keyword in opinion)
            elif factor == "执行可行性":
                execution_keywords = ["执行", "资源", "时间", "风险", "指标", "计划"]
                score = 0.6 + 0.4 * sum(1 for keyword in execution_keywords if keyword in opinion)
            else:  # 创新潜力
                innovation_keywords = ["创新", "技术", "模式", "机会", "突破", "差异化"]
                score = 0.65 + 0.35 * sum(1 for keyword in innovation_keywords if keyword in opinion)
            return min(1.0, max(0.5, score))
    
    def _generate_decision_advice(self, issue: str, decision: bool, scores: Dict[str, float], sage_opinions: Dict[str, str]) -> str:
        """生成决策建议
        
        Args:
            issue: 决策议题
            decision: 决策结果
            scores: 各因素评分
            sage_opinions: 三贤者的意见
            
        Returns:
            决策建议
        """
        try:
            from zeroclaw_integration import ZeroClawIntegration
            zero_claw = ZeroClawIntegration()
            
            # 构建建议生成请求
            opinions_text = "\n".join([f"{sage}: {opinion}" for sage, opinion in sage_opinions.items()])
            scores_text = "\n".join([f"{factor}: {score:.2f}" for factor, score in scores.items()])
            
            prompt = f"基于以下信息，为议题'{issue}'生成详细的决策建议：\n\n决策结果：{'通过' if decision else '否决'}\n\n各因素评分：\n{scores_text}\n\n三贤者意见：\n{opinions_text}\n\n请提供详细的决策建议，包括具体的行动方案和注意事项。"
            
            # 调用大模型生成建议
            advice = zero_claw.call_llm(prompt, model="glm")
            return advice
        except Exception as e:
            print(f"[三贤者] 生成决策建议失败: {e}")
            # 失败时使用默认建议
            if decision:
                advice = f"基于三贤者的共识分析，建议批准 '{issue}'。"
                
                # 根据评分提供具体建议
                if scores["战略价值"] > 0.8:
                    advice += " 战略层面分析充分，具有长期发展潜力。"
                if scores["执行可行性"] > 0.8:
                    advice += " 执行计划可行，资源配置合理。"
                if scores["创新潜力"] > 0.8:
                    advice += " 创新思路突出，有望形成竞争优势。"
                
                advice += " 建议按照三贤者的具体建议制定详细实施计划，定期评估进展。"
            else:
                advice = f"基于三贤者的共识分析，建议暂缓 '{issue}'。"
                
                # 分析不足
                if scores["战略价值"] < 0.7:
                    advice += " 战略层面需要进一步完善，建议重新评估市场定位。"
                if scores["执行可行性"] < 0.7:
                    advice += " 执行计划存在风险，建议优化资源配置和时间表。"
                if scores["创新潜力"] < 0.7:
                    advice += " 创新思路不够突出，建议探索更多可能性。"
                
                advice += " 建议根据三贤者的意见进行修改后重新提交决策。"
            return advice
    
    def call_llm_api(self, prompt: str, model_name: str = "glm") -> Optional[str]:
        """调用大模型API
        
        Args:
            prompt: 提示词
            model_name: 模型名称
            
        Returns:
            模型生成的文本
        """
        try:
            # 尝试使用ZeroClaw作为外部服务（如果可用）
            try:
                from zeroclaw_integration import ZeroClawIntegration
                zero_claw = ZeroClawIntegration()
                return zero_claw.call_llm(prompt, model=model_name)
            except ImportError:
                # 如果ZeroClaw不可用，使用其他LLM接口
                print(f"[三贤者] ZeroClaw不可用，使用备用LLM接口")
                # 这里可以添加其他LLM接口的实现
                return f"[模拟响应] 针对问题 '{prompt}' 的分析和建议"
        except Exception as e:
            print(f"[三贤者] 调用大模型失败: {e}")
            return None
