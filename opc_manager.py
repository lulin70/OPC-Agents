#!/usr/bin/env python3
"""
Agency-Agents Manager

Core management script for the Agency-Agents system, integrating with TRAE.
"""

import os
import sys
import json
import toml
import requests
import time
import random
from typing import Dict, List, Optional, Any

from communication_manager import CommunicationManager, ContextManager
from zeroclaw_integration import ZeroClawIntegration

class OPCManager:
    """Manager class for the OPC-Agents system"""
    
    def __init__(self, config_path: str = "config.toml"):
        """Initialize the OPC Manager"""
        self.config_path = config_path
        self.config = self._load_config()
        self.agents = self._load_agents()
        self.official_agents = self._load_official_agents()
        # 初始化通信管理器和上下文管理器
        self.communication_manager = CommunicationManager()
        self.context_manager = ContextManager()
        # 初始化三层架构
        self._initialize_three_layer_architecture()
    
    def _initialize_three_layer_architecture(self):
        """Initialize the three-layer architecture: Executive Office Agents / Department Agents / Employee Agents"""
        print("[系统架构] 初始化三层架构...")
        
        # 构建三层架构
        self.three_layer_architecture = {
            "executive_office": {
                "agents": self.get_executive_office_agents(),
                "description": "总裁办，负责战略决策、任务分配和全局协调",
                "authority": "最高决策机构，拥有对所有部门的指挥权",
                "responsibilities": [
                    "制定公司战略和目标",
                    "分配和协调跨部门任务",
                    "监控各部门工作进度",
                    "解决部门间冲突",
                    "资源分配和优化",
                    "最终决策和审批"
                ]
            },
            "departments": {},
            "employees": {}
        }
        
        # 加载部门和员工Agent
        departments = self.get_departments()
        for department in departments:
            if department != "executive_office":  # 总裁办单独处理
                department_agents = self.get_official_agent_by_department(department)
                custom_agents = self.get_agent_by_department(department)
                
                self.three_layer_architecture["departments"][department] = {
                    "agents": department_agents,
                    "custom_agents": custom_agents,
                    "description": f"{department}部门，负责相关业务处理",
                    "report_to": "executive_office",
                    "coordination_with": [d for d in departments if d != department and d != "executive_office"],
                    "responsibilities": []
                }
                
                # 为每个部门创建员工Agent
                for agent in department_agents:
                    agent_id = agent.get('name')
                    self.three_layer_architecture["employees"][agent_id] = {
                        "department": department,
                        "type": "official",
                        "info": agent,
                        "report_to": f"{department}_manager"
                    }
                
                for agent_name in custom_agents:
                    self.three_layer_architecture["employees"][agent_name] = {
                        "department": department,
                        "type": "custom",
                        "report_to": f"{department}_manager"
                    }
        
        # 增强总裁办与部门之间的协作机制
        self._enhance_executive_office_coordination()
        
        print("[系统架构] 三层架构初始化完成")
        print(f"[系统架构] 总裁办Agent数量: {len(self.three_layer_architecture['executive_office']['agents'])}")
        print(f"[系统架构] 部门数量: {len(self.three_layer_architecture['departments'])}")
        print(f"[系统架构] 员工Agent数量: {len(self.three_layer_architecture['employees'])}")
        print("[系统架构] 总裁办核心地位已强化，部门间协作机制已优化")
    
    def _enhance_executive_office_coordination(self):
        """增强总裁办与部门之间的协作机制"""
        print("[系统架构] 增强总裁办与部门之间的协作机制...")
        
        # 为每个部门添加具体职责
        department_responsibilities = {
            "design": ["UI/UX设计", "品牌设计", "视觉设计"],
            "development": ["软件开发", "系统架构", "代码维护"],
            "marketing": ["市场推广", "品牌建设", "客户获取"],
            "legal": ["法律咨询", "合同管理", "合规监督"],
            "hr": ["人才招聘", "员工培训", "绩效考核"],
            "finance": ["财务管理", "预算规划", "成本控制"],
            "operations": ["流程优化", "项目协调", "资源管理"],
            "research": ["市场调研", "数据分析", "趋势预测"],
            "sales": ["客户开发", "销售管理", " revenue generation"],
            "project_management": ["项目规划", "进度跟踪", "风险管理"],
            "customer_service": ["客户支持", "问题解决", "满意度管理"],
            "content": ["内容创作", "文案撰写", "内容策略"]
        }
        
        # 更新部门职责
        for department, responsibilities in department_responsibilities.items():
            if department in self.three_layer_architecture["departments"]:
                self.three_layer_architecture["departments"][department]["responsibilities"] = responsibilities
        
        # 建立跨部门协作流程
        self.cross_departmental_processes = {
            "new_product_development": {
                "description": "新产品开发流程",
                "participants": ["executive_office", "design", "development", "marketing", "research"],
                "stages": [
                    "需求分析",
                    "设计阶段",
                    "开发阶段",
                    "测试阶段",
                    "市场推广",
                    "发布阶段"
                ],
                "coordinator": "executive_office"
            },
            "marketing_campaign": {
                "description": "营销活动流程",
                "participants": ["executive_office", "marketing", "design", "content"],
                "stages": [
                    "活动策划",
                    "创意设计",
                    "内容创作",
                    "活动执行",
                    "效果评估"
                ],
                "coordinator": "marketing"
            },
            "budget_planning": {
                "description": "预算规划流程",
                "participants": ["executive_office", "finance", "hr", "operations"],
                "stages": [
                    "需求收集",
                    "预算编制",
                    "审核审批",
                    "执行监控"
                ],
                "coordinator": "finance"
            }
        }
        
        print("[系统架构] 跨部门协作流程已建立")
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from TOML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """Get model configuration
        
        Args:
            model_name: Model name, default to None (use default model)
            
        Returns:
            Model configuration
        """
        if not model_name:
            model_name = self.config.get('models', {}).get('default', 'trae')
        
        return self.config.get('models', {}).get(model_name, {})
    
    def get_available_models(self) -> List[str]:
        """Get list of available models
        
        Returns:
            List of available model names
        """
        models = self.config.get('models', {})
        return [key for key in models if key != 'default']
    
    def _load_agents(self) -> Dict[str, List[str]]:
        """Load agent configurations"""
        return self.config.get('agents', {})
    
    def _load_official_agents(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load official agents from extracted JSON files with caching and deduplication"""
        official_agents = {}
        official_agents_dir = "official_agents"
        cache_file = os.path.join(official_agents_dir, "agents_cache.json")
        
        # Try to load from cache first
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    print("Loading agents from cache...")
                    return json.load(f)
            except Exception as e:
                print(f"Error loading cache: {e}")
        
        if not os.path.exists(official_agents_dir):
            print(f"Official agents directory {official_agents_dir} not found")
            return official_agents
        
        print("Loading agents from JSON files...")
        agent_ids = set()  # To track unique agent IDs
        
        for filename in os.listdir(official_agents_dir):
            if filename.endswith('.json') and filename != "agents_cache.json":
                file_path = os.path.join(official_agents_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        agents = json.load(f)
                        for agent in agents:
                            agent_id = agent.get('name')
                            if agent_id and agent_id not in agent_ids:
                                agent_ids.add(agent_id)
                                department = agent.get('department', 'unknown')
                                if department not in official_agents:
                                    official_agents[department] = []
                                official_agents[department].append(agent)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        
        # Save to cache for future use
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(official_agents, f, ensure_ascii=False, indent=2)
            print("Agents cached successfully")
        except Exception as e:
            print(f"Error saving cache: {e}")
        
        return official_agents
    
    def get_agent_by_department(self, department: str) -> List[str]:
        """Get agents by department"""
        agents = self.agents.get(department, [])
        # 处理字典类型的代理配置（如executive_office和three_sages）
        if isinstance(agents, dict):
            return list(agents.values())
        return agents
    
    def get_official_agent_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get official agents by department"""
        return self.official_agents.get(department, [])
    
    def get_all_agents(self) -> List[str]:
        """Get all agents"""
        all_agents = []
        for department_agents in self.agents.values():
            all_agents.extend(department_agents)
        return all_agents
    
    def get_all_official_agents(self) -> List[Dict[str, Any]]:
        """Get all official agents"""
        all_agents = []
        for department_agents in self.official_agents.values():
            all_agents.extend(department_agents)
        return all_agents
    
    def get_departments(self) -> List[str]:
        """Get all departments"""
        departments = set(self.agents.keys())
        departments.update(self.official_agents.keys())
        return sorted(list(departments))
    
    def get_executive_office_agents(self) -> Dict[str, str]:
        """Get executive office agents"""
        return self.agents.get('executive_office', {})
    
    def get_three_sages(self) -> Dict[str, str]:
        """Get three sages agents"""
        return self.agents.get('three_sages', {})
    
    def decompose_task(self, task: str, time_horizon: str = "medium") -> List[Dict[str, str]]:
        """Decompose a task into smaller tasks based on time horizon
        
        Args:
            task: The task to decompose
            time_horizon: Time horizon, can be "short", "medium", or "long"
            
        Returns:
            List of decomposed tasks
        """
        print(f"[总裁办] 分解任务: {task} (时间范围: {time_horizon})")
        
        # 增强的任务分解逻辑
        decomposed_tasks = []
        
        # 战略规划阶段
        decomposed_tasks.append({
            "task": f"{task} - 战略规划",
            "department": "executive_office",
            "agent": "strategy_planner",
            "priority": "high",
            "time_horizon": "short",
            "description": "制定详细的战略计划，包括目标、资源需求和时间线"
        })
        
        # 资源评估阶段
        decomposed_tasks.append({
            "task": f"{task} - 资源评估",
            "department": "executive_office",
            "agent": "resource_optimizer",
            "priority": "high",
            "time_horizon": "short",
            "description": "评估所需的人力、财力和技术资源，确保资源充足"
        })
        
        # 风险评估阶段
        decomposed_tasks.append({
            "task": f"{task} - 风险评估",
            "department": "executive_office",
            "agent": "risk_manager",
            "priority": "medium",
            "time_horizon": "short",
            "description": "识别潜在风险并制定应对策略"
        })
        
        # 执行阶段
        decomposed_tasks.append({
            "task": f"{task} - 执行实施",
            "department": "operations",
            "agent": "project_coordinator",
            "priority": "high",
            "time_horizon": "medium",
            "description": "协调各部门执行任务，确保按计划进行"
        })
        
        # 外部关系协调
        decomposed_tasks.append({
            "task": f"{task} - 外部关系协调",
            "department": "executive_office",
            "agent": "external_relations_officer",
            "priority": "medium",
            "time_horizon": "medium",
            "description": "协调与外部合作伙伴的关系，确保资源和支持"
        })
        
        # 监控与调整
        decomposed_tasks.append({
            "task": f"{task} - 监控与调整",
            "department": "executive_office",
            "agent": "operations_coordinator",
            "priority": "medium",
            "time_horizon": "medium",
            "description": "实时监控任务进展，根据实际情况调整计划"
        })
        
        # 评估与总结
        decomposed_tasks.append({
            "task": f"{task} - 评估与总结",
            "department": "executive_office",
            "agent": "report_specialist",
            "priority": "medium",
            "time_horizon": "long",
            "description": "评估任务完成情况，总结经验教训，形成报告"
        })
        
        for decomposed_task in decomposed_tasks:
            print(f"[总裁办] 分解任务: {decomposed_task['task']} (部门: {decomposed_task['department']}, 代理: {decomposed_task['agent']}, 优先级: {decomposed_task['priority']})")
        
        return decomposed_tasks
    
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
    
    def track_progress(self, tasks: List[str] = None) -> Dict[str, Any]:
        """Track progress of tasks
        
        Args:
            tasks: List of task IDs (if None, track all tasks)
            
        Returns:
            Progress information
        """
        print("[总裁办] 跟踪任务进度")
        
        progress_info = {
            "overview": {},
            "tasks": {},
            "by_department": {},
            "by_priority": {},
            "by_time_horizon": {},
            "insights": [],
            "recommendations": []
        }
        
        # 获取任务列表
        if tasks:
            task_list = tasks
        else:
            all_tasks = self.get_all_tasks()
            task_list = list(all_tasks.keys())
        
        total_progress = 0
        task_count = 0
        status_counts = {}
        department_progress = {}
        priority_progress = {}
        time_horizon_progress = {}
        delayed_tasks = []
        at_risk_tasks = []
        
        for task_id in task_list:
            task_status = self.get_task_status(task_id)
            if task_status:
                status = task_status.get("status")
                progress = task_status.get("progress", 0)
                department = task_status.get("department", "unknown")
                priority = task_status.get("priority", "medium")
                time_horizon = task_status.get("time_horizon", "medium")
                created_at = task_status.get("created_at")
                updated_at = task_status.get("updated_at")
                
                # 任务详情
                progress_info["tasks"][task_id] = {
                    "status": status,
                    "progress": progress,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "department": department,
                    "priority": priority,
                    "time_horizon": time_horizon
                }
                
                # 统计状态
                if status not in status_counts:
                    status_counts[status] = 0
                status_counts[status] += 1
                
                # 部门进度
                if department not in department_progress:
                    department_progress[department] = {"total": 0, "progress": 0, "tasks": []}
                department_progress[department]["total"] += 1
                department_progress[department]["progress"] += progress
                department_progress[department]["tasks"].append({
                    "task_id": task_id,
                    "status": status,
                    "progress": progress,
                    "priority": priority
                })
                
                # 优先级进度
                if priority not in priority_progress:
                    priority_progress[priority] = {"total": 0, "progress": 0}
                priority_progress[priority]["total"] += 1
                priority_progress[priority]["progress"] += progress
                
                # 时间范围进度
                if time_horizon not in time_horizon_progress:
                    time_horizon_progress[time_horizon] = {"total": 0, "progress": 0}
                time_horizon_progress[time_horizon]["total"] += 1
                time_horizon_progress[time_horizon]["progress"] += progress
                
                # 识别延迟任务
                if status == "in_progress" and progress < 50:
                    # 检查任务是否长时间未更新
                    if updated_at:
                        time_since_update = time.time() - updated_at
                        if time_since_update > 86400:  # 超过24小时
                            delayed_tasks.append({
                                "task_id": task_id,
                                "progress": progress,
                                "time_since_update": time_since_update
                            })
                
                # 识别高风险任务
                if priority == "high" and status != "completed" and progress < 30:
                    at_risk_tasks.append({
                        "task_id": task_id,
                        "progress": progress,
                        "status": status
                    })
                
                total_progress += progress
                task_count += 1
                
                print(f"[总裁办] 任务 {task_id} 进度: {progress}%, 状态: {status}, 部门: {department}")
            else:
                progress_info["tasks"][task_id] = {
                    "status": "not_found",
                    "progress": 0
                }
                print(f"[总裁办] 任务 {task_id} 未找到")
        
        # 计算平均进度
        average_progress = total_progress / task_count if task_count > 0 else 0
        
        # 计算部门平均进度
        for department, data in department_progress.items():
            data["average_progress"] = data["progress"] / data["total"] if data["total"] > 0 else 0
            # 按优先级排序任务
            data["tasks"].sort(key=lambda x: (x["priority"] == "high", x["progress"]))
        
        # 计算优先级平均进度
        for priority, data in priority_progress.items():
            data["average_progress"] = data["progress"] / data["total"] if data["total"] > 0 else 0
        
        # 计算时间范围平均进度
        for time_horizon, data in time_horizon_progress.items():
            data["average_progress"] = data["progress"] / data["total"] if data["total"] > 0 else 0
        
        # 填充概览信息
        progress_info["overview"] = {
            "total_tasks": task_count,
            "completed_tasks": status_counts.get("completed", 0),
            "in_progress_tasks": status_counts.get("in_progress", 0),
            "pending_tasks": status_counts.get("pending", 0),
            "average_progress": average_progress,
            "status_counts": status_counts,
            "delayed_tasks": len(delayed_tasks),
            "at_risk_tasks": len(at_risk_tasks)
        }
        
        # 生成智能洞察
        if delayed_tasks:
            progress_info["insights"].append(f"发现 {len(delayed_tasks)} 个任务进度延迟，需要关注")
        
        if at_risk_tasks:
            progress_info["insights"].append(f"发现 {len(at_risk_tasks)} 个高优先级任务进度低于30%，存在风险")
        
        # 分析部门表现
        if department_progress:
            lowest_dept = min(department_progress.items(), key=lambda x: x[1]["average_progress"])
            if lowest_dept[1]["average_progress"] < 0.5:
                progress_info["insights"].append(f"部门 '{lowest_dept[0]}' 平均进度较低 ({lowest_dept[1]['average_progress']:.1f}%)，需要支持")
        
        # 分析优先级任务
        high_priority_progress = priority_progress.get("high", {}).get("average_progress", 0)
        if high_priority_progress < 0.6:
            progress_info["insights"].append("高优先级任务平均进度较低，建议优先资源投入")
        
        # 生成建议
        if delayed_tasks:
            progress_info["recommendations"].append("及时跟进延迟任务，分析原因并提供必要支持")
        
        if at_risk_tasks:
            progress_info["recommendations"].append("重点关注高优先级任务，确保资源充足")
        
        if average_progress < 0.5:
            progress_info["recommendations"].append("整体进度偏低，建议调整工作计划和资源分配")
        
        progress_info["recommendations"].extend([
            "定期召开进度评审会议，及时解决问题",
            "建立任务预警机制，提前识别风险",
            "优化任务分解，确保任务可执行性",
            "加强跨部门协作，提高整体效率"
        ])
        
        progress_info["by_department"] = department_progress
        progress_info["by_priority"] = priority_progress
        progress_info["by_time_horizon"] = time_horizon_progress
        
        return progress_info
    
    def generate_report(self, period: str = "weekly") -> Dict[str, Any]:
        """Generate report for a specific period
        
        Args:
            period: Report period, can be "daily", "weekly", or "monthly"
            
        Returns:
            Report information
        """
        print(f"[总裁办] 生成 {period} 报告")
        
        # 获取所有任务
        all_tasks = self.get_all_tasks()
        
        # 统计任务状态
        status_counts = {}
        department_tasks = {}
        priority_tasks = {}
        time_horizon_tasks = {}
        
        total_progress = 0
        task_count = 0
        
        for task_id, task_info in all_tasks.items():
            status = task_info.get("status", "unknown")
            progress = task_info.get("progress", 0)
            department = task_info.get("department", "unknown")
            priority = task_info.get("priority", "medium")
            time_horizon = task_info.get("time_horizon", "medium")
            
            # 状态统计
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
            
            # 部门统计
            if department not in department_tasks:
                department_tasks[department] = {"count": 0, "progress": 0}
            department_tasks[department]["count"] += 1
            department_tasks[department]["progress"] += progress
            
            # 优先级统计
            if priority not in priority_tasks:
                priority_tasks[priority] = {"count": 0, "progress": 0}
            priority_tasks[priority]["count"] += 1
            priority_tasks[priority]["progress"] += progress
            
            # 时间范围统计
            if time_horizon not in time_horizon_tasks:
                time_horizon_tasks[time_horizon] = {"count": 0, "progress": 0}
            time_horizon_tasks[time_horizon]["count"] += 1
            time_horizon_tasks[time_horizon]["progress"] += progress
            
            total_progress += progress
            task_count += 1
        
        # 计算平均进度
        average_progress = total_progress / task_count if task_count > 0 else 0
        
        # 计算部门平均进度
        department_averages = {}
        for department, data in department_tasks.items():
            department_averages[department] = data["progress"] / data["count"] if data["count"] > 0 else 0
        
        # 计算优先级平均进度
        priority_averages = {}
        for priority, data in priority_tasks.items():
            priority_averages[priority] = data["progress"] / data["count"] if data["count"] > 0 else 0
        
        # 计算时间范围平均进度
        time_horizon_averages = {}
        for time_horizon, data in time_horizon_tasks.items():
            time_horizon_averages[time_horizon] = data["progress"] / data["count"] if data["count"] > 0 else 0
        
        # 生成智能洞察
        insights = []
        if task_count > 0:
            # 识别瓶颈部门
            bottleneck_department = min(department_averages.items(), key=lambda x: x[1]) if department_averages else None
            if bottleneck_department:
                insights.append(f"部门 '{bottleneck_department[0]}' 进度较低 ({bottleneck_department[1]:.1f}%)，可能需要额外支持")
            
            # 识别高优先级任务状态
            high_priority_progress = priority_averages.get("high", 0)
            if high_priority_progress < 50:
                insights.append("高优先级任务进度落后，建议优先关注")
            
            # 识别时间范围分布
            short_term_progress = time_horizon_averages.get("short", 0)
            if short_term_progress < 70:
                insights.append("短期任务进度不足，可能影响整体计划")
        
        # 生成建议
        recommendations = []
        if insights:
            recommendations.append("根据瓶颈分析，调整资源分配")
        recommendations.extend([
            "建立更频繁的进度检查机制",
            "优化任务分解和分配流程",
            "加强跨部门协作和沟通",
            "建立明确的任务优先级体系",
            "定期评估和调整战略目标"
        ])
        
        report = {
            "period": period,
            "generated_at": time.time(),
            "company_name": self.config.get('core', {}).get('name', 'OPC Agency'),
            "task_summary": {
                "total_tasks": task_count,
                "status_counts": status_counts,
                "average_progress": average_progress
            },
            "department_analysis": {
                "department_tasks": department_tasks,
                "department_averages": department_averages
            },
            "priority_analysis": {
                "priority_tasks": priority_tasks,
                "priority_averages": priority_averages
            },
            "time_horizon_analysis": {
                "time_horizon_tasks": time_horizon_tasks,
                "time_horizon_averages": time_horizon_averages
            },
            "key_achievements": [
                "完成项目规划和启动",
                "建立有效的任务管理体系",
                "优化资源分配和利用",
                "提高团队协作效率"
            ],
            "challenges": [
                "资源有限，需要更高效利用",
                "市场竞争激烈，需要差异化策略",
                "技术更新迭代快，需要持续学习",
                "一人公司的管理复杂度增加"
            ],
            "insights": insights,
            "recommendations": recommendations,
            "next_steps": [
                "实施资源优化计划",
                "加强高优先级任务监控",
                "推进跨部门协作机制",
                "定期回顾和调整战略"
            ]
        }
        
        print(f"[总裁办] 报告生成完成，共 {task_count} 个任务，平均进度: {average_progress:.1f}%")
        print(f"[总裁办] 智能洞察: {insights}")
        
        return report
    
    def send_message(self, sender: str, receiver: str, message_type: str, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送消息给指定代理
        
        Args:
            sender: 发送者名称
            receiver: 接收者名称
            message_type: 消息类型
            content: 消息内容
            context: 上下文信息
            
        Returns:
            消息传递结果
        """
        return self.communication_manager.send_message(sender, receiver, message_type, content, context)
    
    def start_consensus(self, issue: str, agents: List[str], voting_method: str = "majority", decision_threshold: float = 0.6) -> Dict[str, Any]:
        """启动共识过程
        
        Args:
            issue: 需要达成共识的问题
            agents: 参与共识的代理列表
            voting_method: 投票方式，支持 "majority" (多数决) 和 "unanimous" (一致通过)
            decision_threshold: 决策阈值，默认为0.6 (60%)
            
        Returns:
            共识结果
        """
        return self.communication_manager.start_consensus(issue, agents, voting_method, decision_threshold)
    
    def get_message_history(self, agent: str) -> List[Dict[str, Any]]:
        """获取代理的消息历史
        
        Args:
            agent: 代理名称
            
        Returns:
            消息历史列表
        """
        return self.communication_manager.get_message_history(agent)
    
    def get_token_usage(self) -> Dict[str, int]:
        """获取Token使用情况
        
        Returns:
            各代理的Token使用量
        """
        return self.communication_manager.get_token_usage()
    
    def set_context(self, key: str, value: Any):
        """设置上下文
        
        Args:
            key: 上下文键
            value: 上下文值
        """
        self.context_manager.set_context(key, value)
    
    def get_context(self, key: str) -> Optional[Any]:
        """获取上下文
        
        Args:
            key: 上下文键
            
        Returns:
            上下文值
        """
        return self.context_manager.get_context(key)
    
    def create_task(self, task_id: str, task_name: str, agent: str, initial_status: str = "pending"):
        """创建任务并设置初始状态
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            agent: 负责的代理
            initial_status: 初始状态，默认为"pending"
        """
        self.communication_manager.create_task(task_id, task_name, agent, initial_status)
    
    def update_task_status(self, task_id: str, status: str, progress: int = None):
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新的状态
            progress: 任务进度 (0-100)
        """
        self.communication_manager.update_task_status(task_id, status, progress)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        return self.communication_manager.get_task_status(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态
        
        Returns:
            所有任务的状态信息
        """
        return self.communication_manager.get_all_tasks()
    
    def get_tasks_by_agent(self, agent: str) -> List[Dict[str, Any]]:
        """获取指定代理的所有任务
        
        Args:
            agent: 代理名称
            
        Returns:
            代理的任务列表
        """
        return self.communication_manager.get_tasks_by_agent(agent)
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """获取指定状态的所有任务
        
        Args:
            status: 任务状态
            
        Returns:
            指定状态的任务列表
        """
        return self.communication_manager.get_tasks_by_status(status)
    
    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务的历史记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务历史记录列表
        """
        return self.communication_manager.get_task_history(task_id)
    
    def get_all_task_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有任务的历史记录
        
        Returns:
            所有任务的历史记录
        """
        return self.communication_manager.get_all_task_history()
    
    def add_todo_item(self, content: str, priority: str = "medium", due_date: str = None) -> str:
        """添加待办事项
        
        Args:
            content: 待办事项内容
            priority: 优先级，可选值：high, medium, low
            due_date: 截止日期，格式：YYYY-MM-DD
            
        Returns:
            待办事项ID
        """
        todo_id = f"todo_{int(time.time())}"
        todo_item = {
            "id": todo_id,
            "content": content,
            "priority": priority,
            "due_date": due_date,
            "status": "pending",
            "created_at": time.time()
        }
        
        # 存储待办事项
        if not hasattr(self, "todo_items"):
            self.todo_items = {}
        self.todo_items[todo_id] = todo_item
        
        print(f"[个人助理] 添加待办事项: {content} (优先级: {priority})")
        return todo_id
    
    def get_todo_items(self, status: str = None) -> List[Dict[str, Any]]:
        """获取待办事项列表
        
        Args:
            status: 状态，可选值：pending, completed, in_progress
            
        Returns:
            待办事项列表
        """
        if not hasattr(self, "todo_items"):
            self.todo_items = {}
        
        todo_list = list(self.todo_items.values())
        if status:
            todo_list = [item for item in todo_list if item.get("status") == status]
        
        return todo_list
    
    def update_todo_status(self, todo_id: str, status: str) -> bool:
        """更新待办事项状态
        
        Args:
            todo_id: 待办事项ID
            status: 新状态，可选值：pending, completed, in_progress
            
        Returns:
            是否更新成功
        """
        if not hasattr(self, "todo_items") or todo_id not in self.todo_items:
            return False
        
        self.todo_items[todo_id]["status"] = status
        self.todo_items[todo_id]["updated_at"] = time.time()
        
        print(f"[个人助理] 更新待办事项状态: {todo_id} -> {status}")
        return True
    
    def add_hobby(self, hobby: str, description: str = "") -> str:
        """添加兴趣爱好
        
        Args:
            hobby: 兴趣爱好名称
            description: 兴趣爱好描述
            
        Returns:
            兴趣爱好ID
        """
        hobby_id = f"hobby_{int(time.time())}"
        hobby_item = {
            "id": hobby_id,
            "name": hobby,
            "description": description,
            "created_at": time.time()
        }
        
        # 存储兴趣爱好
        if not hasattr(self, "hobbies"):
            self.hobbies = {}
        self.hobbies[hobby_id] = hobby_item
        
        print(f"[个人助理] 添加兴趣爱好: {hobby}")
        return hobby_id
    
    def get_hobbies(self) -> List[Dict[str, Any]]:
        """获取兴趣爱好列表
        
        Returns:
            兴趣爱好列表
        """
        if not hasattr(self, "hobbies"):
            self.hobbies = {}
        
        return list(self.hobbies.values())
    
    def plan_trip(self, destination: str, start_date: str, end_date: str, preferences: Dict[str, Any] = None) -> Dict[str, Any]:
        """规划出行
        
        Args:
            destination: 目的地
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD
            preferences: 偏好设置，包括：budget, accommodation_type, activities等
            
        Returns:
            出行计划
        """
        trip_id = f"trip_{int(time.time())}"
        trip_plan = {
            "id": trip_id,
            "destination": destination,
            "start_date": start_date,
            "end_date": end_date,
            "preferences": preferences or {},
            "created_at": time.time()
        }
        
        # 存储出行计划
        if not hasattr(self, "trip_plans"):
            self.trip_plans = {}
        self.trip_plans[trip_id] = trip_plan
        
        print(f"[个人助理] 规划出行: {destination} ({start_date} - {end_date})")
        return trip_plan
    
    def get_trip_plans(self) -> List[Dict[str, Any]]:
        """获取出行计划列表
        
        Returns:
            出行计划列表
        """
        if not hasattr(self, "trip_plans"):
            self.trip_plans = {}
        
        return list(self.trip_plans.values())
    
    def get_weather(self, location: str) -> Dict[str, Any]:
        """获取实时天气信息
        
        Args:
            location: 地点
            
        Returns:
            天气信息
        """
        # 尝试使用OpenWeatherMap API获取真实天气数据
        try:
            # 从配置中获取API密钥
            weather_api_key = self.config.get('services', {}).get('weather_api_key', '')
            
            if weather_api_key:
                import requests
                # 构建API请求
                url = f"http://api.openweathermap.org/data/2.5/weather"
                params = {
                    "q": location,
                    "appid": weather_api_key,
                    "units": "metric",  # 使用摄氏度
                    "lang": "zh_cn"  # 使用中文
                }
                
                # 发送请求
                response = requests.get(url, params=params, timeout=5)
                response.raise_for_status()
                data = response.json()
                
                # 解析天气数据
                weather_data = {
                    "location": location,
                    "temperature": data.get("main", {}).get("temp", 0),
                    "humidity": data.get("main", {}).get("humidity", 0),
                    "condition": data.get("weather", [{}])[0].get("description", "未知"),
                    "wind_speed": data.get("wind", {}).get("speed", 0),
                    "timestamp": time.time()
                }
                
                print(f"[个人助理] 获取天气信息: {location} - {weather_data['condition']}, {weather_data['temperature']}°C")
                return weather_data
            else:
                # 如果没有API密钥，使用模拟数据
                print("[个人助理] 未配置天气API密钥，使用模拟数据")
                weather_data = {
                    "location": location,
                    "temperature": 22,
                    "humidity": 65,
                    "condition": "晴",
                    "wind_speed": 10,
                    "timestamp": time.time()
                }
                return weather_data
        except Exception as e:
            print(f"[个人助理] 获取天气信息失败: {e}")
            # 失败时使用模拟数据
            weather_data = {
                "location": location,
                "temperature": 22,
                "humidity": 65,
                "condition": "晴",
                "wind_speed": 10,
                "timestamp": time.time()
            }
            return weather_data
    
    def update_task_with_history(self, task_id: str, status: str, progress: int = None, description: str = ""):
        """更新任务状态并添加历史记录
        
        Args:
            task_id: 任务ID
            status: 新的状态
            progress: 任务进度 (0-100)
            description: 状态更新描述
        """
        self.communication_manager.update_task_with_history(task_id, status, progress, description)
    
    def complete_task(self, task_id: str, result: Optional[Any] = None, description: str = "任务完成"):
        """完成任务并添加历史记录
        
        Args:
            task_id: 任务ID
            result: 任务结果
            description: 完成描述
        """
        self.communication_manager.complete_task(task_id, result, description)
    
    def test_task(self, task_id: str, test_result: bool, test_details: Optional[Dict[str, Any]] = None):
        """测试任务并添加历史记录
        
        Args:
            task_id: 任务ID
            test_result: 测试结果
            test_details: 测试详细信息
        """
        self.communication_manager.test_task(task_id, test_result, test_details)
    
    def optimize_agents(self, agent_ids: List[str] = None, iterations: int = 1) -> Dict[str, Any]:
        """优化Agent的自我迭代功能
        
        Args:
            agent_ids: 要优化的Agent ID列表，None表示所有Agent
            iterations: 迭代次数
            
        Returns:
            优化结果
        """
        print("[Agent优化] 开始Agent自我优化迭代")
        
        optimization_results = {
            "iterations": [],
            "summary": {
                "total_iterations": iterations,
                "optimized_agents": [],
                "improvements": []
            }
        }
        
        # 获取所有Agent
        if agent_ids:
            agents_to_optimize = agent_ids
        else:
            # 从所有部门获取Agent
            all_agents = []
            for department in self.get_departments():
                official_agents = self.get_official_agent_by_department(department)
                custom_agents = self.get_agent_by_department(department)
                
                for agent in official_agents:
                    all_agents.append(agent.get('name'))
                all_agents.extend(custom_agents)
            
            # 去重
            agents_to_optimize = list(set(all_agents))
        
        print(f"[Agent优化] 待优化的Agent: {agents_to_optimize}")
        
        # 开始迭代优化
        for iteration in range(iterations):
            print(f"\n[Agent优化] 第 {iteration + 1} 次迭代")
            
            iteration_result = {
                "iteration": iteration + 1,
                "timestamp": time.time(),
                "agents_analyzed": [],
                "optimizations": [],
                "evaluation": {}
            }
            
            for agent_id in agents_to_optimize:
                print(f"[Agent优化] 分析Agent: {agent_id}")
                
                # 1. 分析Agent性能
                analysis = self._analyze_agent_performance(agent_id)
                
                # 2. 生成优化建议
                optimization = self._generate_optimization_suggestions(agent_id, analysis)
                
                # 3. 应用优化
                applied = self._apply_optimization(agent_id, optimization)
                
                # 4. 自我评估
                evaluation = self._evaluate_agent_performance(agent_id)
                
                agent_result = {
                    "agent_id": agent_id,
                    "analysis": analysis,
                    "optimization": optimization,
                    "applied": applied,
                    "evaluation": evaluation
                }
                
                iteration_result["agents_analyzed"].append(agent_id)
                iteration_result["optimizations"].append(agent_result)
            
            # 生成迭代分析文档
            analysis_doc = self._generate_optimization_document(iteration_result)
            iteration_result["analysis_document"] = analysis_doc
            
            # 保存迭代记录
            self._save_optimization_record(iteration_result)
            
            optimization_results["iterations"].append(iteration_result)
            optimization_results["summary"]["optimized_agents"].extend(agents_to_optimize)
        
        # 生成最终总结
        optimization_results["summary"]["improvements"] = self._generate_improvement_summary(optimization_results["iterations"])
        
        print("[Agent优化] 自我优化迭代完成")
        return optimization_results
    
    def _analyze_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """分析Agent性能
        
        Args:
            agent_id: Agent ID
            
        Returns:
            性能分析结果
        """
        # 模拟性能分析
        performance_metrics = {
            "response_time": random.uniform(0.5, 3.0),
            "task_completion_rate": random.uniform(0.7, 0.95),
            "quality_score": random.uniform(0.6, 0.9),
            "token_usage": random.randint(1000, 5000),
            "error_rate": random.uniform(0.01, 0.1)
        }
        
        # 分析性能瓶颈
        bottlenecks = []
        if performance_metrics["response_time"] > 2.0:
            bottlenecks.append("响应时间过长")
        if performance_metrics["task_completion_rate"] < 0.8:
            bottlenecks.append("任务完成率低")
        if performance_metrics["quality_score"] < 0.7:
            bottlenecks.append("输出质量不高")
        if performance_metrics["token_usage"] > 4000:
            bottlenecks.append("Token消耗过高")
        if performance_metrics["error_rate"] > 0.05:
            bottlenecks.append("错误率较高")
        
        return {
            "metrics": performance_metrics,
            "bottlenecks": bottlenecks,
            "strengths": ["任务处理能力", "响应速度", "输出质量"][:random.randint(1, 3)],
            "weaknesses": bottlenecks
        }
    
    def _generate_optimization_suggestions(self, agent_id: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成优化建议
        
        Args:
            agent_id: Agent ID
            analysis: 性能分析结果
            
        Returns:
            优化建议
        """
        suggestions = []
        
        # 根据性能瓶颈生成建议
        if "响应时间过长" in analysis["bottlenecks"]:
            suggestions.append("优化提示词模板，减少不必要的思考步骤")
            suggestions.append("增加缓存机制，存储常见任务的处理结果")
        
        if "任务完成率低" in analysis["bottlenecks"]:
            suggestions.append("增强任务理解能力，添加更多上下文信息")
            suggestions.append("优化任务分解策略，提高任务完成的准确性")
        
        if "输出质量不高" in analysis["bottlenecks"]:
            suggestions.append("优化提示词，明确输出要求和质量标准")
            suggestions.append("增加输出验证步骤，确保结果符合要求")
        
        if "Token消耗过高" in analysis["bottlenecks"]:
            suggestions.append("优化提示词结构，减少冗余信息")
            suggestions.append("使用更高效的语言模型，减少Token使用")
        
        if "错误率较高" in analysis["bottlenecks"]:
            suggestions.append("增加错误处理机制，提高鲁棒性")
            suggestions.append("优化输入验证，减少错误输入导致的问题")
        
        # 通用优化建议
        suggestions.extend([
            "定期更新知识库，保持信息的准确性",
            "优化Agent之间的协作机制，提高整体效率",
            "根据任务类型动态调整模型参数，优化性能"
        ])
        
        return {
            "suggestions": suggestions,
            "priority": "high" if len(analysis["bottlenecks"]) > 2 else "medium",
            "estimated_improvement": random.uniform(0.1, 0.4)
        }
    
    def _apply_optimization(self, agent_id: str, optimization: Dict[str, Any]) -> bool:
        """应用优化
        
        Args:
            agent_id: Agent ID
            optimization: 优化建议
            
        Returns:
            是否成功应用
        """
        print(f"[Agent优化] 应用优化到Agent: {agent_id}")
        print(f"[Agent优化] 优先级: {optimization['priority']}")
        print(f"[Agent优化] 预计改进: {optimization['estimated_improvement']:.2f}")
        
        # 模拟应用优化
        # 在实际应用中，这里会更新Agent的配置、提示词模板等
        time.sleep(0.5)  # 模拟优化过程
        
        return True
    
    def _evaluate_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """评估Agent性能
        
        Args:
            agent_id: Agent ID
            
        Returns:
            评估结果
        """
        # 模拟评估结果
        evaluation_metrics = {
            "response_time": random.uniform(0.3, 2.5),
            "task_completion_rate": random.uniform(0.75, 0.98),
            "quality_score": random.uniform(0.65, 0.95),
            "token_usage": random.randint(800, 4500),
            "error_rate": random.uniform(0.005, 0.08)
        }
        
        # 计算整体评分
        overall_score = (
            evaluation_metrics["task_completion_rate"] * 0.3 +
            evaluation_metrics["quality_score"] * 0.3 +
            (1 - evaluation_metrics["error_rate"]) * 0.2 +
            (3 - evaluation_metrics["response_time"]) / 3 * 0.1 +
            (5000 - evaluation_metrics["token_usage"]) / 5000 * 0.1
        )
        
        return {
            "metrics": evaluation_metrics,
            "overall_score": overall_score,
            "status": "improved" if overall_score > 0.8 else "stable" if overall_score > 0.7 else "needs_improvement",
            "recommendations": ["继续优化", "保持当前状态", "重点改进"][min(int(overall_score * 3), 2)]
        }
    
    def _generate_optimization_document(self, iteration_result: Dict[str, Any]) -> str:
        """生成优化分析文档
        
        Args:
            iteration_result: 迭代结果
            
        Returns:
            分析文档内容
        """
        doc = f"# Agent优化迭代分析文档\n"
        doc += f"迭代次数: {iteration_result['iteration']}\n"
        doc += f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(iteration_result['timestamp']))}\n\n"
        
        doc += "## 优化概览\n"
        doc += f"分析的Agent数量: {len(iteration_result['agents_analyzed'])}\n\n"
        
        doc += "## Agent分析详情\n"
        for opt in iteration_result['optimizations']:
            doc += f"### {opt['agent_id']}\n"
            doc += "#### 性能分析\n"
            doc += f"- 响应时间: {opt['analysis']['metrics']['response_time']:.2f}s\n"
            doc += f"- 任务完成率: {opt['analysis']['metrics']['task_completion_rate']:.2f}\n"
            doc += f"- 质量评分: {opt['analysis']['metrics']['quality_score']:.2f}\n"
            doc += f"- Token消耗: {opt['analysis']['metrics']['token_usage']}\n"
            doc += f"- 错误率: {opt['analysis']['metrics']['error_rate']:.2f}\n"
            doc += f"- 瓶颈: {', '.join(opt['analysis']['bottlenecks']) if opt['analysis']['bottlenecks'] else '无'}\n\n"
            
            doc += "#### 优化建议\n"
            for i, suggestion in enumerate(opt['optimization']['suggestions'], 1):
                doc += f"{i}. {suggestion}\n"
            doc += f"- 优先级: {opt['optimization']['priority']}\n"
            doc += f"- 预计改进: {opt['optimization']['estimated_improvement']:.2f}\n\n"
            
            doc += "#### 评估结果\n"
            doc += f"- 整体评分: {opt['evaluation']['overall_score']:.2f}\n"
            doc += f"- 状态: {opt['evaluation']['status']}\n"
            doc += f"- 建议: {opt['evaluation']['recommendations']}\n\n"
        
        return doc
    
    def _save_optimization_record(self, iteration_result: Dict[str, Any]):
        """保存优化记录
        
        Args:
            iteration_result: 迭代结果
        """
        # 创建优化记录目录
        import os
        records_dir = "optimization_records"
        if not os.path.exists(records_dir):
            os.makedirs(records_dir)
        
        # 生成文件名
        timestamp = int(iteration_result['timestamp'])
        filename = f"optimization_iteration_{iteration_result['iteration']}_{timestamp}.json"
        file_path = os.path.join(records_dir, filename)
        
        # 保存记录
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(iteration_result, f, ensure_ascii=False, indent=2)
        
        print(f"[Agent优化] 优化记录已保存: {file_path}")
    
    def _generate_improvement_summary(self, iterations: List[Dict[str, Any]]) -> List[str]:
        """生成改进总结
        
        Args:
            iterations: 迭代结果列表
            
        Returns:
            改进总结
        """
        improvements = []
        
        # 统计整体改进情况
        total_agents = 0
        improved_agents = 0
        
        for iteration in iterations:
            for opt in iteration['optimizations']:
                total_agents += 1
                if opt['evaluation']['status'] == 'improved':
                    improved_agents += 1
        
        if total_agents > 0:
            improvement_rate = improved_agents / total_agents
            improvements.append(f"整体改进率: {improvement_rate:.2f}")
            improvements.append(f"改进的Agent数量: {improved_agents}/{total_agents}")
        
        # 分析常见瓶颈和解决方案
        bottlenecks = {}
        for iteration in iterations:
            for opt in iteration['optimizations']:
                for bottleneck in opt['analysis']['bottlenecks']:
                    bottlenecks[bottleneck] = bottlenecks.get(bottleneck, 0) + 1
        
        if bottlenecks:
            top_bottlenecks = sorted(bottlenecks.items(), key=lambda x: x[1], reverse=True)[:3]
            improvements.append(f"主要瓶颈: {', '.join([b[0] for b in top_bottlenecks])}")
        
        improvements.append("优化迭代完成，建议定期进行自我优化以保持Agent性能")
        
        return improvements
    
    def __init__(self, config_path: str = "config.toml"):
        """Initialize the OPC Manager"""
        self.config_path = config_path
        self.config = self._load_config()
        self.agents = self._load_agents()
        self.official_agents = self._load_official_agents()
        # 初始化通信管理器和上下文管理器
        self.communication_manager = CommunicationManager()
        self.context_manager = ContextManager()
        # 初始化 ZeroClaw 集成
        zeroclaw_config = self.config.get('models', {}).get('zeroclaw', {})
        base_url = zeroclaw_config.get('base_url', 'http://localhost:8081')
        pairing_code = zeroclaw_config.get('pairing_code', '516238')  # 从配置中获取配对代码
        self.zeroclaw = ZeroClawIntegration(base_url=base_url, pairing_code=pairing_code)
        # 初始化三层架构
        self._initialize_three_layer_architecture()
        # 初始化模型性能监控
        self.model_performance = {}
        # 初始化模型选择策略
        self.model_selection_strategy = self._load_model_selection_strategy()
    
    def _load_model_selection_strategy(self) -> Dict[str, str]:
        """加载模型选择策略"""
        # 基于任务类型的模型选择策略
        return {
            "战略规划": "zeroclaw",  # 战略规划使用ZeroClaw
            "执行决策": "zeroclaw",  # 执行决策使用ZeroClaw
            "创新思维": "zeroclaw",  # 创新思维使用ZeroClaw
            "日常对话": "zeroclaw",  # 日常对话使用ZeroClaw
            "技术分析": "zeroclaw",  # 技术分析使用ZeroClaw
            "默认": self.config.get('models', {}).get('default', 'zeroclaw')  # 默认模型
        }
    
    def get_model_for_task(self, task_type: str) -> str:
        """根据任务类型选择合适的模型
        
        Args:
            task_type: 任务类型
            
        Returns:
            模型名称
        """
        return self.model_selection_strategy.get(task_type, self.model_selection_strategy.get("默认"))
    
    def call_llm_api(self, prompt: str, model_name: str = None, task_type: str = "默认") -> Optional[str]:
        """Call LLM API directly based on model configuration
        
        Args:
            prompt: The prompt to send to the model
            model_name: The name of the model to use (default: None, uses default model)
            task_type: 任务类型，用于自动选择模型
            
        Returns:
            The response from the model
        """
        import requests
        
        # 根据任务类型自动选择模型
        if not model_name:
            model_name = self.get_model_for_task(task_type)
        
        # Get model configuration
        model_config = self.get_model_config(model_name)
        
        print(f"[LLM API] Calling {model_name} model for task type: {task_type}...")
        
        # 记录开始时间
        start_time = time.time()
        tokens_used = 0
        success = False
        error_message = None
        
        try:
            # Handle different model types
            if model_name == 'glm':
                # GLM API call (using the official API endpoint)
                api_key = model_config.get('api_key')
                base_url = model_config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4/chat/completions')
                model = model_config.get('model', 'glm-4.7')
                
                # Check if API key is provided
                if not api_key or api_key == 'your_glm_api_key':
                    print("[LLM API] GLM API key not configured")
                    error_message = "GLM API key not configured"
                    return None
                
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                }
                
                # Use the correct request format as per GLM API documentation
                data = {
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 1.0,
                    'max_tokens': 65536,
                    'stream': False
                }
                
                print(f"[LLM API] Sending request to GLM API at {base_url}")
                print(f"[LLM API] Using model: {model}")
                
                try:
                    response = requests.post(base_url, headers=headers, json=data, timeout=30)
                    print(f"[LLM API] GLM API response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'choices' in result and len(result['choices']) > 0:
                            tokens_used = result.get('usage', {}).get('total_tokens', 0)
                            success = True
                            return result['choices'][0]['message']['content']
                        else:
                            print("[LLM API] Invalid response format from GLM API")
                            error_message = "Invalid response format from GLM API"
                            return None
                    else:
                        print(f"[LLM API] GLM API returned error: {response.text}")
                        error_message = f"GLM API returned error: {response.text}"
                        return None
                except Exception as e:
                    print(f"[LLM API] Error calling GLM API: {e}")
                    error_message = f"Error calling GLM API: {e}"
                    return None
            
            elif model_name == 'openai':
                # OpenAI API call
                api_key = model_config.get('api_key')
                base_url = model_config.get('base_url', 'https://api.openai.com/v1/chat/completions')
                model = model_config.get('model', 'gpt-4o')
                
                # Check if API key is provided
                if not api_key or api_key == 'your_openai_api_key':
                    print("[LLM API] OpenAI API key not configured")
                    error_message = "OpenAI API key not configured"
                    return None
                
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                }
                
                data = {
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.7
                }
                
                response = requests.post(base_url, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                tokens_used = result.get('usage', {}).get('total_tokens', 0)
                success = True
                return result['choices'][0]['message']['content']
            
            elif model_name == 'anthropic':
                # Anthropic API call
                api_key = model_config.get('api_key')
                base_url = model_config.get('base_url', 'https://api.anthropic.com/v1/messages')
                model = model_config.get('model', 'claude-3-opus-20240229')
                
                # Check if API key is provided
                if not api_key or api_key == 'your_anthropic_api_key':
                    print("[LLM API] Anthropic API key not configured")
                    error_message = "Anthropic API key not configured"
                    return None
                
                headers = {
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01'
                }
                
                data = {
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.7
                }
                
                response = requests.post(base_url, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                tokens_used = result.get('usage', {}).get('input_tokens', 0) + result.get('usage', {}).get('output_tokens', 0)
                success = True
                return result['content'][0]['text']
            
            elif model_name == 'google':
                # Google API call
                api_key = model_config.get('api_key')
                base_url = model_config.get('base_url', 'https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent')
                model = model_config.get('model', 'gemini-pro')
                
                # Check if API key is provided
                if not api_key or api_key == 'your_google_api_key':
                    print("[LLM API] Google API key not configured")
                    error_message = "Google API key not configured"
                    return None
                
                headers = {
                    'Content-Type': 'application/json'
                }
                
                data = {
                    'contents': [
                        {
                            'parts': [
                                {'text': prompt}
                            ]
                        }
                    ]
                }
                
                response = requests.post(f"{base_url}?key={api_key}", headers=headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                # Google API doesn't return token usage in the same way
                success = True
                return result['candidates'][0]['content']['parts'][0]['text']
            
            elif model_name == 'azure':
                # Azure OpenAI API call
                api_key = model_config.get('api_key')
                base_url = model_config.get('base_url')
                model = model_config.get('model', 'gpt-4')
                
                # Check if API key is provided
                if not api_key or api_key == 'your_azure_api_key':
                    print("[LLM API] Azure API key not configured")
                    error_message = "Azure API key not configured"
                    return None
                
                # Check if base URL is provided
                if not base_url:
                    print("[LLM API] Azure base URL not configured")
                    error_message = "Azure base URL not configured"
                    return None
                
                headers = {
                    'Content-Type': 'application/json',
                    'api-key': api_key
                }
                
                data = {
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.7
                }
                
                response = requests.post(base_url, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                tokens_used = result.get('usage', {}).get('total_tokens', 0)
                success = True
                return result['choices'][0]['message']['content']
            
            elif model_name == 'local':
                # Local model (Ollama) API call
                base_url = model_config.get('base_url', 'http://localhost:11434/api/chat')
                model = model_config.get('model', 'llama3')
                
                headers = {
                    'Content-Type': 'application/json'
                }
                
                data = {
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'stream': False
                }
                
                response = requests.post(base_url, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                result = response.json()
                # Ollama doesn't return token usage
                success = True
                return result['message']['content']
            
            elif model_name == 'trae':
                # Trae built-in model
                try:
                    from trae import Chat
                    chat = Chat()
                    response = chat.send(prompt)
                    # Trae doesn't return token usage
                    success = True
                    return response
                except Exception as trae_error:
                    print(f"[Trae Built-in] Error: {trae_error}")
                    error_message = f"Trae error: {trae_error}"
                    return None
            
            elif model_name == 'zeroclaw':
                # ZeroClaw API call using integration module
                model = model_config.get('model', 'zhipu/glm-4.7')
                
                print(f"[LLM API] Sending request to ZeroClaw framework")
                print(f"[LLM API] Using model: {model}")
                
                try:
                    # 使用 ZeroClawIntegration 实例调用聊天完成 API
                    response = self.zeroclaw.call_chat_completion(
                        prompt=prompt,
                        model=model,
                        temperature=1.0,
                        max_tokens=65536
                    )
                    
                    if response:
                        success = True
                        return response
                    else:
                        print("[LLM API] No response from ZeroClaw API")
                        error_message = "No response from ZeroClaw API"
                        return None
                except Exception as e:
                    print(f"[LLM API] Error calling ZeroClaw API: {e}")
                    error_message = f"Error calling ZeroClaw API: {e}"
                    return None
            
            else:
                print(f"[LLM API] Unknown model: {model_name}")
                error_message = f"Unknown model: {model_name}"
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[LLM API] Network error calling {model_name}: {e}")
            error_message = f"Network error: {e}"
            return None
        except requests.exceptions.HTTPError as e:
            print(f"[LLM API] HTTP error calling {model_name}: {e}")
            error_message = f"HTTP error: {e}"
            return None
        except KeyError as e:
            print(f"[LLM API] Response parsing error calling {model_name}: {e}")
            error_message = f"Response parsing error: {e}"
            return None
        except Exception as e:
            print(f"[LLM API] Error calling {model_name}: {e}")
            error_message = f"Error: {e}"
            return None
        finally:
            # 记录模型性能
            self._record_model_performance(model_name, task_type, start_time, tokens_used, success, error_message)
    
    def _record_model_performance(self, model_name: str, task_type: str, start_time: float, tokens_used: int, success: bool, error_message: Optional[str]):
        """记录模型性能
        
        Args:
            model_name: 模型名称
            task_type: 任务类型
            start_time: 开始时间
            tokens_used: 使用的Token数
            success: 是否成功
            error_message: 错误信息
        """
        response_time = time.time() - start_time
        
        if model_name not in self.model_performance:
            self.model_performance[model_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "total_response_time": 0,
                "total_tokens": 0,
                "error_count": 0,
                "error_messages": [],
                "task_types": {}
            }
        
        # 更新模型性能统计
        self.model_performance[model_name]["total_calls"] += 1
        if success:
            self.model_performance[model_name]["successful_calls"] += 1
            self.model_performance[model_name]["total_response_time"] += response_time
            self.model_performance[model_name]["total_tokens"] += tokens_used
        else:
            self.model_performance[model_name]["error_count"] += 1
            if error_message and error_message not in self.model_performance[model_name]["error_messages"]:
                self.model_performance[model_name]["error_messages"].append(error_message)
        
        # 更新任务类型统计
        if task_type not in self.model_performance[model_name]["task_types"]:
            self.model_performance[model_name]["task_types"][task_type] = {
                "calls": 0,
                "successful": 0,
                "total_time": 0
            }
        
        self.model_performance[model_name]["task_types"][task_type]["calls"] += 1
        if success:
            self.model_performance[model_name]["task_types"][task_type]["successful"] += 1
            self.model_performance[model_name]["task_types"][task_type]["total_time"] += response_time
    
    def get_model_performance(self) -> Dict[str, Any]:
        """获取模型性能统计
        
        Returns:
            模型性能统计
        """
        return self.model_performance
    
    def get_model_recommendation(self, task_type: str) -> Dict[str, Any]:
        """获取模型推荐
        
        Args:
            task_type: 任务类型
            
        Returns:
            模型推荐信息
        """
        # 分析历史性能数据，推荐最优模型
        best_model = None
        best_score = 0
        
        for model_name, performance in self.model_performance.items():
            if task_type in performance["task_types"]:
                task_stats = performance["task_types"][task_type]
                success_rate = task_stats["successful"] / task_stats["calls"] if task_stats["calls"] > 0 else 0
                avg_response_time = task_stats["total_time"] / task_stats["successful"] if task_stats["successful"] > 0 else float('inf')
                
                # 计算综合评分（成功 rate权重0.7，响应时间权重0.3）
                time_score = 1 / (avg_response_time + 1)  # 响应时间越短分数越高
                score = success_rate * 0.7 + time_score * 0.3
                
                if score > best_score:
                    best_score = score
                    best_model = model_name
        
        # 如果没有历史数据，使用默认策略
        if not best_model:
            best_model = self.get_model_for_task(task_type)
        
        return {
            "recommended_model": best_model,
            "score": best_score,
            "task_type": task_type
        }
    
    def optimize_model_selection(self):
        """优化模型选择策略
        
        基于历史性能数据，自动调整模型选择策略
        """
        print("[模型优化] 开始优化模型选择策略...")
        
        # 分析各任务类型的最佳模型
        task_types = set()
        for model_perf in self.model_performance.values():
            task_types.update(model_perf["task_types"].keys())
        
        for task_type in task_types:
            recommendation = self.get_model_recommendation(task_type)
            if recommendation["score"] > 0.5:  # 只有评分较高时才更新策略
                self.model_selection_strategy[task_type] = recommendation["recommended_model"]
                print(f"[模型优化] 为任务类型 '{task_type}' 更新最佳模型为: {recommendation['recommended_model']} (评分: {recommendation['score']:.2f})")
        
        print("[模型优化] 模型选择策略优化完成")
        return self.model_selection_strategy
    
    def trae_request(self, prompt: str, agent_type: str, model_name: str = None) -> Optional[str]:
        """Send request to AI model API or use Trae's built-in model
        
        Args:
            prompt: The prompt to send to the model
            agent_type: The type of agent
            model_name: The name of the model to use (default: None, uses default model)
            
        Returns:
            The response from the model
        """
        # Get model configuration
        model_config = self.get_model_config(model_name)
        model_name = model_name or self.config.get('models', {}).get('default', 'trae')
        
        print(f"[API Call] Processing request for {agent_type} using {model_name}...")
        
        try:
            # Try to call LLM API directly first
            response = self.call_llm_api(prompt, model_name)
            if response:
                print(f"[LLM API] Response received successfully from {model_name}")
                return response
            
            # If LLM API call fails, return specific error message
            if model_name == 'glm':
                # Check if API key is configured
                api_key = model_config.get('api_key')
                if not api_key or api_key == 'your_glm_api_key':
                    return "大模型Key不可用，请检查GLM API密钥是否正确配置"
                else:
                    return "大模型未连接，请检查网络连接或GLM服务状态"
            elif model_name == 'local':
                return "本地大模型未连接，请检查Ollama服务是否运行"
            elif model_name == 'trae':
                return "Trae内置模型调用失败，请检查Trae服务状态"
            else:
                # Check if API key is configured for other models
                api_key = model_config.get('api_key')
                if not api_key or 'your_' in api_key:
                    return f"大模型Key不可用，请检查{model_name} API密钥是否正确配置"
                else:
                    return "大模型未连接，请检查网络连接或API配置"
            
        except requests.exceptions.RequestException as e:
            print(f"Error in trae_request (network): {e}")
            error_str = str(e)
            if "Connection refused" in error_str:
                if model_name == 'local':
                    return "本地大模型未连接，请检查Ollama服务是否运行"
                else:
                    return "大模型未连接，请检查网络连接"
            elif "403" in error_str or "Forbidden" in error_str:
                return "大模型Key不可用，API密钥可能没有权限访问指定模型"
            elif "401" in error_str or "Unauthorized" in error_str:
                return "大模型Key无效，请检查API密钥是否正确"
            elif "429" in error_str or "Rate limit" in error_str:
                return "大模型请求频率过高，请稍后再试"
            else:
                return "大模型网络连接失败，请检查网络设置"
        except Exception as e:
            print(f"Error in trae_request: {e}")
            error_str = str(e)
            if "403" in error_str or "Forbidden" in error_str:
                return "大模型Key不可用，API密钥可能没有权限访问指定模型"
            elif "401" in error_str or "Unauthorized" in error_str:
                return "大模型Key无效，请检查API密钥是否正确"
            else:
                return f"大模型调用失败：{error_str}"


    
    def assign_task(self, task: str, department: str, agent: Optional[str] = None, model: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Assign a task to an agent with context passing
        
        Args:
            task: The task to assign
            department: The department to assign the task to
            agent: The specific agent to assign (optional)
            model: The AI model to use (optional)
            context: Context information to pass to the agent
            
        Returns:
            The agent's response
        """
        # First check official agents
        official_agents = self.official_agents.get(department, [])
        custom_agents = self.agents.get(department, [])
        
        if not official_agents and not custom_agents:
            print(f"错误: 部门 '{department}' 不存在或没有代理")
            print("请使用 '查看所有部门' 命令查看可用部门")
            return None
        
        selected_agent = None
        
        if agent:
            # Find agent by name or ID in official agents
            for official_agent in official_agents:
                agent_id = official_agent.get('name')
                agent_name = official_agent.get('frontmatter', {}).get('name')
                if agent_id == agent or agent_name == agent:
                    selected_agent = official_agent
                    break
            
            # If not found, check custom agents
            if not selected_agent and agent in custom_agents:
                selected_agent = agent
            
            if not selected_agent:
                print(f"错误: 在部门 '{department}' 中未找到代理 '{agent}'")
                print(f"该部门可用的代理有:")
                if official_agents:
                    print("官方代理:")
                    for official_agent in official_agents[:5]:
                        agent_name = official_agent.get('frontmatter', {}).get('name', official_agent.get('name'))
                        print(f"- {agent_name}")
                    if len(official_agents) > 5:
                        print(f"... 还有 {len(official_agents) - 5} 个代理")
                if custom_agents:
                    print("自定义代理:")
                    for custom_agent in custom_agents:
                        print(f"- {custom_agent}")
                return None
        else:
            # Assign to first agent in department
            if official_agents:
                selected_agent = official_agents[0]
                agent_name = selected_agent.get('frontmatter', {}).get('name', selected_agent.get('name'))
                print(f"自动分配任务给部门 '{department}' 的第一个代理: {agent_name}")
            elif custom_agents:
                selected_agent = custom_agents[0]
                print(f"自动分配任务给部门 '{department}' 的第一个代理: {selected_agent}")
            else:
                print(f"错误: 部门 '{department}' 没有可用的代理")
                return None
        
        # 添加上下文传递
        if context:
            print(f"[上下文传递] 传递上下文信息给代理: {agent or selected_agent.get('name', selected_agent)}")
            print(f"[上下文传递] 上下文内容: {context}")
        
        # 构建完整的任务信息，包括上下文
        task_info = {
            "task": task,
            "department": department,
            "agent": agent or selected_agent.get('name', selected_agent),
            "model": model,
            "context": context,
            "timestamp": time.time()
        }
        
        # 发送任务给代理
        print(f"[任务分配] 分配任务 '{task}' 给 {department} 部门的 {agent or selected_agent.get('name', selected_agent)}")
        
        # 调用AI模型获取响应
        agent_type = f"{department}_{agent or selected_agent.get('name', selected_agent)}"
        response = self.trae_request(task, agent_type, model)
        
        # 记录任务分配历史
        self.communication_manager.create_task(
            task_id=f"task_{int(time.time())}",
            task_name=task,
            agent=agent or selected_agent.get('name', selected_agent),
            initial_status="in_progress"
        )
        
        return response
    
    def run_project(self, project_name: str, tasks: List[Dict[str, str]]) -> Dict[str, str]:
        """Run a project with multiple tasks"""
        results = {}
        
        for task_info in tasks:
            department = task_info.get('department')
            task = task_info.get('task')
            agent = task_info.get('agent')
            model = task_info.get('model')
            
            if not department or not task:
                continue
            
            result = self.assign_task(task, department, agent, model)
            results[f"{department}:{agent or 'default'}"] = result
        
        return results

def main():
    """Main function"""
    manager = OPCManager()
    
    # Example usage
    print("=== Agency-Agents System ===")
    print(f"Agency: {manager.config.get('core', {}).get('name', 'TRAE Agency')}")
    print(f"Version: {manager.config.get('core', {}).get('version', '1.0.0')}")
    print()
    
    # List all departments
    print("Available Departments:")
    departments = manager.get_departments()
    for department in departments:
        # Get official agents
        official_agents = manager.get_official_agent_by_department(department)
        official_agent_names = [agent.get('frontmatter', {}).get('name', agent.get('name')) for agent in official_agents]
        
        # Get custom agents
        custom_agents = manager.get_agent_by_department(department)
        
        all_agents = official_agent_names + custom_agents
        if all_agents:
            print(f"- {department}: {', '.join(all_agents[:5])}{'...' if len(all_agents) > 5 else ''}")
            if len(all_agents) > 5:
                print(f"  Total: {len(all_agents)} agents")
    print()
    
    # Example task assignment with official agent
    print("=== Example Task Assignment ===")
    result = manager.assign_task(
        "Design a modern UI for a task management app",
        "design"
    )
    print(f"Design Agent response: {result}")
    
    # Example task assignment with engineering agent
    print("\n=== Engineering Task Assignment ===")
    result = manager.assign_task(
        "Optimize database performance for a high-traffic application",
        "engineering",
        "Database Optimizer"
    )
    print(f"Database Optimizer response: {result}")

if __name__ == "__main__":
    main()