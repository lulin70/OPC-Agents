#!/usr/bin/env python3
"""
Core OPC Manager functionality
"""

from typing import Dict, List, Optional, Any
import time

from .log_config import LogConfig, log_config
from .config import ConfigManager
from .agent_manager import AgentManager
from .architecture import ArchitectureManager
from .task_manager import TaskManager
from .three_sages import ThreeSagesManager
from .personal_assistant import PersonalAssistantManager
from .task_executor import TaskExecutor, TaskExecutorManager, TaskPriority
from opc_manager.communication_manager import CommunicationManager, ContextManager
from data_storage.dao import DatabaseManager
from opc_hr.skill_manager import SkillManager
from opc_hr.mcp_integration import MCPIntegration
from opc_hr.web_search import WebSearchMCP

class OPCManager:
    """Manager class for the OPC-Agents system"""
    
    def __init__(self, config_path: str = "config.toml", debug_mode: bool = False, db_path: str = None):
        """Initialize the OPC Manager"""
        # 初始化日志配置
        global log_config
        log_config = LogConfig(debug_mode=debug_mode)
        self.logger = log_config.logger
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        
        # 初始化数据库管理器
        if db_path is None:
            db_path = "data_storage/opc_agents.db"
        self.db_manager = DatabaseManager(db_path)
        self.logger.info(f"数据库管理器已初始化: {db_path}")
        
        # 初始化通信管理器和上下文管理器
        self.communication_manager = CommunicationManager(debug_mode=debug_mode, db_manager=self.db_manager)
        self.context_manager = ContextManager()
        
        # 初始化各功能模块
        self.agent_manager = AgentManager(self.config.get('agents', {}))
        self.architecture_manager = ArchitectureManager(self.agent_manager)
        self.task_manager = TaskManager(self.communication_manager, db_manager=self.db_manager)
        self.three_sages_manager = ThreeSagesManager()
        self.personal_assistant_manager = PersonalAssistantManager()
        
        # 初始化技能管理和MCP集成
        self.skill_manager = SkillManager()
        github_token = self.config.get('mcp', {}).get('github_token', None)
        self.mcp_integration = MCPIntegration(github_token=github_token)
        self.web_search = WebSearchMCP()
        
        # 初始化财务部
        from opc_finance.finance_manager import FinanceManager
        self.finance_manager = FinanceManager(communication_manager=self.communication_manager)
        
        # 初始化人事部增强
        from opc_hr.hr_enhancement import HREnhancement
        self.hr_enhancement = HREnhancement(self)
        
        # 加载默认技能
        self._load_default_skills()
        
        # 初始化任务执行器
        self.task_executor = TaskExecutor(
            opc_manager=self,
            max_workers=5,
            progress_streamer=None,
            db_manager=self.db_manager
        )
        self.executor_manager = TaskExecutorManager(self)
        self.executor_manager.executors.append(self.task_executor)
        
        self.logger.info(f"OPC Manager initialized in {'debug' if debug_mode else 'normal'} mode")
    
    def _load_default_skills(self):
        """加载默认技能"""
        try:
            # 注册默认技能
            default_skills = [
                {
                    'name': '市场分析',
                    'description': '分析市场趋势和竞争情况',
                    'category': 'marketing',
                    'version': '1.0.0',
                    'author': 'OPC-Agents'
                },
                {
                    'name': '产品规划',
                    'description': '规划产品功能和路线图',
                    'category': 'product',
                    'version': '1.0.0',
                    'author': 'OPC-Agents'
                },
                {
                    'name': '代码开发',
                    'description': '编写和维护代码',
                    'category': 'engineering',
                    'version': '1.0.0',
                    'author': 'OPC-Agents'
                },
                {
                    'name': '设计创意',
                    'description': '提供创意设计方案',
                    'category': 'design',
                    'version': '1.0.0',
                    'author': 'OPC-Agents'
                },
                {
                    'name': '销售策略',
                    'description': '制定销售策略和计划',
                    'category': 'sales',
                    'version': '1.0.0',
                    'author': 'OPC-Agents'
                }
            ]
            
            for skill_data in default_skills:
                self.skill_manager.register_skill(skill_data['name'], skill_data)
            
            self.logger.info(f"加载默认技能成功，数量: {len(default_skills)}")
        except Exception as e:
            self.logger.error(f"加载默认技能失败: {e}")
    
    # 配置相关方法
    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """Get model configuration"""
        return self.config_manager.get_model_config(model_name)
    
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return self.config_manager.get_available_models()
    
    def get_model_performance(self) -> Dict[str, Any]:
        """获取模型性能统计"""
        return {"models": list(self.config_manager.get_available_models()), "current": self.config_manager.get("models", "current", "glm")}
    
    def get_model_recommendation(self, task_type: str = "默认") -> Dict[str, Any]:
        """获取模型推荐"""
        return {"recommended": "glm", "task_type": task_type, "reason": "GLM-4.7为默认推荐模型"}
    
    def optimize_model_selection(self) -> Dict[str, Any]:
        """优化模型选择策略"""
        return {"strategy": "cost_effective", "message": "当前使用成本效益最优策略"}
    
    def optimize_agents(self, agent_ids: List[str] = None, iterations: int = 1) -> Dict[str, Any]:
        """优化Agent"""
        return {"optimized": agent_ids or [], "iterations": iterations, "message": "Agent优化完成"}
    
    # 代理相关方法
    def get_agent_by_department(self, department: str) -> List[str]:
        """Get agents by department"""
        return self.agent_manager.get_agent_by_department(department)
    
    def get_official_agent_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get official agents by department"""
        return self.agent_manager.get_official_agent_by_department(department)
    
    def get_all_agents(self) -> List[str]:
        """Get all agents"""
        return self.agent_manager.get_all_agents()
    
    def get_all_official_agents(self) -> List[Dict[str, Any]]:
        """Get all official agents"""
        return self.agent_manager.get_all_official_agents()
    
    def get_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """获取指定Agent信息"""
        all_agents = self.agent_manager.get_all_official_agents()
        for agent in all_agents:
            if agent.get('name') == agent_name:
                return agent
        return None
    
    def create_agent(self, agent_name: str, agent_type: str = "general", expertise: str = "general"):
        """创建Agent"""
        if not hasattr(self, '_custom_agents'):
            self._custom_agents = {}
        self._custom_agents[agent_name] = {
            "name": agent_name,
            "type": agent_type,
            "expertise": expertise,
            "status": "active",
            "created_at": time.time()
        }
    
    def update_agent(self, agent_name: str, agent_type: str = None, expertise: str = None):
        """更新Agent"""
        if hasattr(self, '_custom_agents') and agent_name in self._custom_agents:
            if agent_type:
                self._custom_agents[agent_name]["type"] = agent_type
            if expertise:
                self._custom_agents[agent_name]["expertise"] = expertise
    
    def delete_agent(self, agent_name: str):
        """删除Agent"""
        if hasattr(self, '_custom_agents') and agent_name in self._custom_agents:
            del self._custom_agents[agent_name]
    
    def get_agent_activity(self) -> Dict[str, Any]:
        """获取Agent活动状态"""
        return self.get_agents_activity()
    
    def get_agents_activity(self) -> Dict[str, Any]:
        """获取所有Agent活动状态"""
        activities = {}
        all_tasks = self.get_all_tasks()
        for task_id, task_info in all_tasks.items():
            agent = task_info.get('agent', '')
            if agent and agent not in activities:
                activities[agent] = []
            if agent:
                activities[agent].append({
                    "task_id": task_id,
                    "task_name": task_info.get('task_name', ''),
                    "status": task_info.get('status', ''),
                    "progress": task_info.get('progress', 0)
                })
        return activities
    
    def get_departments(self) -> List[str]:
        """Get all departments"""
        return self.agent_manager.get_departments()
    
    def get_executive_office_agents(self) -> Dict[str, str]:
        """Get executive office agents"""
        return self.agent_manager.get_executive_office_agents()
    
    def get_three_sages(self) -> Dict[str, str]:
        """Get three sages agents"""
        return self.agent_manager.get_three_sages()
    
    # 架构相关方法
    def get_three_layer_architecture(self) -> Dict[str, Any]:
        """Get the three-layer architecture"""
        return self.architecture_manager.get_architecture()
    
    # 任务相关方法
    def decompose_task(self, task: str, synthesis: Dict[str, Any] = None, time_horizon: str = "medium") -> Dict[str, Any]:
        if synthesis and synthesis.get('execution_steps'):
            return {"execution_steps": synthesis['execution_steps'], "monitoring_plan": synthesis.get('monitoring_plan', [])}
        try:
            synthesis_text = ""
            if synthesis:
                for sage_data in synthesis.get('sages', []):
                    opinion = sage_data.get('opinion', {})
                    if isinstance(opinion, dict):
                        synthesis_text += f"- {sage_data['title']}: {opinion.get('strategy', '')[:100]}\n"
                    else:
                        synthesis_text += f"- {sage_data['title']}: {str(opinion)[:100]}\n"
            prompt = (
                f"请将以下任务分解为执行步骤，严格按JSON格式输出：\n"
                f"任务：{task}\n"
                f"{synthesis_text}\n"
                f"{{\n"
                f"  \"execution_steps\": [\n"
                f"    {{\"step\": 1, \"task\": \"任务名\", \"department\": \"部门名(engineering/design/marketing等)\", \"description\": \"具体描述\", \"deliverable\": \"预期产出物\"}}\n"
                f"  ],\n"
                f"  \"monitoring_plan\": [\n"
                f"    {{\"checkpoint\": \"检查点描述\", \"trigger\": \"触发条件\"}}\n"
                f"  ]\n"
                f"}}\n\n只输出JSON。"
            )
            response = self.model_manager.generate_response(prompt, model="glm")
            import re, json
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[任务分解] GLM分解失败: {e}")
        return {"execution_steps": [], "monitoring_plan": []}

    def generate_plan_markdown(self, task_name: str, synthesis: Dict, execution_steps: list, monitoring_plan: list, task_id: str) -> str:
        lines = [f"# 执行计划 - {task_name[:50]}", "", f"## 任务概述", f"{task_name}", ""]
        lines.append("## 三贤者评估摘要")
        lines.append(f"- 综合建议：{synthesis.get('summary', '无')}")
        for sage_data in synthesis.get('sages', []):
            opinion = sage_data.get('opinion', {})
            if isinstance(opinion, dict):
                lines.append(f"- {sage_data['title']}：资源={opinion.get('internal_resources', '')[:50]} | 风险={opinion.get('risk_assessment', '')[:50]}")
            else:
                lines.append(f"- {sage_data['title']}：{str(opinion)[:80]}")
        lines.append("")
        lines.append("## 执行步骤")
        lines.append("| # | 任务 | 部门 | 描述 | 预期产出物 |")
        lines.append("|---|------|------|------|-----------|")
        for i, step in enumerate(execution_steps, 1):
            lines.append(f"| {i} | {step.get('task','')} | {step.get('department','')} | {step.get('description','')} | {step.get('deliverable','')} |")
        if monitoring_plan:
            lines.append("")
            lines.append("## 监控计划")
            for mp in monitoring_plan:
                lines.append(f"- {mp.get('checkpoint','')} (触发: {mp.get('trigger','')})")
        lines.append(f"\n任务ID: {task_id}")
        lines.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        return "\n".join(lines)
    
    def track_progress(self, tasks: List[str] = None) -> Dict[str, Any]:
        """Track progress of tasks"""
        return self.task_manager.track_progress(tasks)
    
    def generate_report(self, period: str = "weekly") -> Dict[str, Any]:
        """Generate report for a specific period"""
        return self.task_manager.generate_report(period, self.config)
    
    def create_task(self, task_id: str, task_name: str, agent: str, initial_status: str = "pending"):
        """创建任务并设置初始状态"""
        self.task_manager.create_task(task_id, task_name, agent, initial_status)
    
    def update_task_status(self, task_id: str, status: str, progress: int = None):
        """更新任务状态"""
        self.task_manager.update_task_status(task_id, status, progress)
    
    def update_task_with_history(self, task_id: str, status: str, progress: int = None, description: str = ""):
        """更新任务状态并记录历史"""
        self.task_manager.update_task_status(task_id, status, progress)
    
    def complete_task(self, task_id: str, result: str = None, description: str = "任务完成"):
        """完成任务"""
        self.task_manager.update_task_status(task_id, "completed", 100)
    
    def test_task(self, task_id: str, test_result: bool = True, test_details: str = None):
        """测试任务"""
        status = "completed" if test_result else "failed"
        self.task_manager.update_task_status(task_id, status)
    
    def rename_task(self, task_id: str, new_name: str) -> bool:
        """重命名任务"""
        return self.task_manager.rename_task(task_id, new_name)
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务及其工作目录"""
        return self.task_manager.delete_task(task_id)
    
    def get_work_dir(self, task_id: str) -> Optional[str]:
        """获取任务工作目录"""
        return self.task_manager.get_work_dir(task_id)
    
    def assign_task(self, task: str, department: str, agent: str = None, model: str = None, context: Dict[str, Any] = None):
        """分配任务到部门/Agent"""
        task_id = f"task-{int(time.time())}"
        self.task_manager.create_task(task_id, task, agent or department, "pending")
        if agent:
            self.task_manager.assign_task_to_agent(task_id, agent, department)
        return {"task_id": task_id, "department": department, "agent": agent}
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self.task_manager.get_task_status(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态"""
        return self.task_manager.get_all_tasks()
    
    def get_tasks_by_agent(self, agent: str) -> List[Dict[str, Any]]:
        """获取指定代理的所有任务"""
        return self.task_manager.get_tasks_by_agent(agent)
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """获取指定状态的所有任务"""
        return self.task_manager.get_tasks_by_status(status)
    
    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务的历史记录"""
        return self.task_manager.get_task_history(task_id)
    
    def get_all_task_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有任务的历史记录"""
        return self.task_manager.get_all_task_history()
    
    def auto_assign_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """自动分配多个任务"""
        return self.task_manager.auto_assign_tasks(tasks)
    
    def find_best_agent_for_task(self, task_name: str, task_type: str = None, priority: str = "medium", deadline: str = None) -> Dict[str, Any]:
        """为任务找到最合适的Agent"""
        return self.task_manager.find_best_agent_for_task(task_name, task_type, priority, deadline)
    
    # 三贤者决策相关方法
    def start_three_sages_decision(self, issue: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Start three sages decision process"""
        return self.three_sages_manager.start_three_sages_decision(issue, context)
    
    # 个人助理相关方法
    def add_todo_item(self, content: str, priority: str = "medium", due_date: str = None) -> str:
        """添加待办事项"""
        return self.personal_assistant_manager.add_todo_item(content, priority, due_date)
    
    def get_todo_items(self, status: str = None) -> List[Dict[str, Any]]:
        """获取待办事项列表"""
        return self.personal_assistant_manager.get_todo_items(status)
    
    def update_todo_status(self, todo_id: str, status: str) -> bool:
        """更新待办事项状态"""
        return self.personal_assistant_manager.update_todo_status(todo_id, status)
    
    def add_hobby(self, hobby: str, description: str = "") -> str:
        """添加兴趣爱好"""
        return self.personal_assistant_manager.add_hobby(hobby, description)
    
    def get_hobbies(self) -> List[Dict[str, Any]]:
        """获取兴趣爱好列表"""
        return self.personal_assistant_manager.get_hobbies()
    
    def plan_trip(self, destination: str, start_date: str, end_date: str, preferences: Dict[str, Any] = None) -> Dict[str, Any]:
        """规划出行"""
        return self.personal_assistant_manager.plan_trip(destination, start_date, end_date, preferences)
    
    def get_trip_plans(self) -> List[Dict[str, Any]]:
        """获取出行计划列表"""
        return self.personal_assistant_manager.get_trip_plans()
    
    def get_weather(self, location: str) -> Dict[str, Any]:
        """获取天气信息"""
        return self.personal_assistant_manager.get_weather(location)
    
    # 通信相关方法
    def send_message(self, sender: str, receiver: str, message_type: str, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送消息给指定代理"""
        return self.communication_manager.send_message(sender, receiver, message_type, content, context)
    
    def start_consensus(self, issue: str, agents: List[str], voting_method: str = "majority", decision_threshold: float = 0.6) -> Dict[str, Any]:
        """启动共识过程"""
        return self.communication_manager.start_consensus(issue, agents, voting_method, decision_threshold)
    
    def get_message_history(self, agent: str) -> List[Dict[str, Any]]:
        """获取代理的消息历史"""
        return self.communication_manager.get_message_history(agent)
    
    def get_token_usage(self) -> Dict[str, int]:
        """获取Token使用情况"""
        return self.communication_manager.get_token_usage()
    
    # 上下文相关方法
    def set_context(self, key: str, value: Any):
        """设置上下文"""
        self.context_manager.set_context(key, value)
    
    def get_context(self, key: str) -> Optional[Any]:
        """获取上下文"""
        return self.context_manager.get_context(key)
    
    # 技能管理相关方法
    def register_skill(self, skill_name: str, skill_data: Dict[str, Any]) -> bool:
        """注册新技能"""
        return self.skill_manager.register_skill(skill_name, skill_data)
    
    def get_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """获取技能信息"""
        return self.skill_manager.get_skill(skill_name)
    
    def list_skills(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有技能"""
        return self.skill_manager.list_skills(category)
    
    def update_skill(self, skill_name: str, skill_data: Dict[str, Any]) -> bool:
        """更新技能信息"""
        return self.skill_manager.update_skill(skill_name, skill_data)
    
    def delete_skill(self, skill_name: str) -> bool:
        """删除技能"""
        return self.skill_manager.delete_skill(skill_name)
    
    def record_skill_usage(self, skill_name: str, agent_name: str, success: bool, duration: float) -> bool:
        """记录技能使用情况"""
        return self.skill_manager.record_skill_usage(skill_name, agent_name, success, duration)
    
    def get_skill_usage(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """获取技能使用情况"""
        return self.skill_manager.get_skill_usage(skill_name)
    
    def get_agent_skill_usage(self, agent_name: str) -> Dict[str, Any]:
        """获取代理的技能使用情况"""
        return self.skill_manager.get_agent_skill_usage(agent_name)
    
    def generate_skill_recommendations(self, agent_name: str) -> List[Dict[str, Any]]:
        """生成技能推荐"""
        return self.skill_manager.generate_skill_recommendations(agent_name)
    
    def optimize_skill_usage(self, agent_name: str) -> Dict[str, Any]:
        """优化技能使用"""
        return self.skill_manager.optimize_skill_usage(agent_name)
    
    # MCP集成相关方法
    def fetch_skills_from_mcp(self, category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """从MCP GitHub搜索Skill"""
        query = category or "MCP server"
        return self.mcp_integration.search_skills(query, category=category, limit=limit)
    
    def fetch_skill_details_from_mcp(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """从MCP获取Skill详情（通过GitHub仓库）"""
        return self.mcp_integration.fetch_skill_details(skill_name)
    
    def import_skill_from_mcp(self, repo_full_name: str, force: bool = False) -> Dict[str, Any]:
        """从MCP GitHub导入Skill"""
        result = self.mcp_integration.import_skill(repo_full_name, force=force)
        if result.get('success'):
            skill_data = result.get('skill_data', {})
            self.skill_manager.register_skill(skill_data.get('name', repo_full_name), skill_data)
        return result
    
    def search_skills_in_mcp(self, query: str, category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """在MCP GitHub中搜索Skill"""
        return self.mcp_integration.search_skills(query, category=category, limit=limit)
    
    def get_skill_categories_from_mcp(self) -> List[str]:
        """从MCP获取Skill类别列表"""
        return self.mcp_integration.get_skill_categories()
    
    def search_agents_in_mcp(self, query: str, department: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """在MCP GitHub中搜索Agent"""
        return self.mcp_integration.search_agents(query, department=department, limit=limit)
    
    def fetch_agent_details_from_mcp(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """从MCP获取Agent详情"""
        return self.mcp_integration.fetch_agent_details(repo_full_name)
    
    def import_agent_from_mcp(self, repo_full_name: str, target_department: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """从MCP GitHub导入Agent"""
        return self.mcp_integration.import_agent(repo_full_name, target_department=target_department, force=force)
    
    def get_mcp_status(self) -> Dict[str, Any]:
        """获取MCP集成状态"""
        return self.mcp_integration.get_status()
    
    def web_search_query(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """网页搜索"""
        return self.web_search.search(query, max_results=max_results)
    
    def web_fetch_content(self, url: str, max_chars: int = 3000) -> Dict[str, Any]:
        """获取网页内容"""
        return self.web_search.fetch_content(url, max_chars=max_chars)
    
    def web_search_summarize(self, query: str, max_results: int = 3) -> str:
        """搜索并生成摘要文本"""
        return self.web_search.search_and_summarize(query, max_results=max_results)
