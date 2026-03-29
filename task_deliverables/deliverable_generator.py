#!/usr/bin/env python3
"""
成果物生成器

提供任务成果物的自动生成、模板管理和格式化功能。
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
import uuid


@dataclass
class DeliverableTemplate:
    """成果物模板"""
    type: str
    name: str
    description: str
    structure: Dict[str, Any]
    required_fields: List[str] = field(default_factory=list)


class DeliverableGenerator:
    """成果物生成器"""
    
    def __init__(self):
        """初始化成果物生成器"""
        self.logger = logging.getLogger(__name__)
        
        # 预定义模板
        self.templates = {
            "analysis_report": DeliverableTemplate(
                type="analysis_report",
                name="分析报告",
                description="数据分析报告模板",
                structure={
                    "title": "",
                    "summary": "",
                    "methodology": "",
                    "findings": [],
                    "conclusions": "",
                    "recommendations": [],
                    "appendix": {}
                },
                required_fields=["title", "summary", "findings", "conclusions"]
            ),
            "product_design": DeliverableTemplate(
                type="product_design",
                name="产品设计文档",
                description="产品设计文档模板",
                structure={
                    "title": "",
                    "overview": "",
                    "requirements": [],
                    "design_specifications": {},
                    "user_stories": [],
                    "wireframes": [],
                    "technical_requirements": {},
                    "timeline": {}
                },
                required_fields=["title", "overview", "requirements"]
            ),
            "project_plan": DeliverableTemplate(
                type="project_plan",
                name="项目计划",
                description="项目计划文档模板",
                structure={
                    "title": "",
                    "objectives": [],
                    "scope": "",
                    "deliverables": [],
                    "timeline": {},
                    "resources": {},
                    "risks": [],
                    "milestones": []
                },
                required_fields=["title", "objectives", "timeline"]
            ),
            "technical_document": DeliverableTemplate(
                type="technical_document",
                name="技术文档",
                description="技术文档模板",
                structure={
                    "title": "",
                    "introduction": "",
                    "architecture": {},
                    "implementation": {},
                    "api_documentation": {},
                    "testing": {},
                    "deployment": {}
                },
                required_fields=["title", "introduction", "architecture"]
            ),
            "meeting_minutes": DeliverableTemplate(
                type="meeting_minutes",
                name="会议纪要",
                description="会议纪要模板",
                structure={
                    "title": "",
                    "date": "",
                    "attendees": [],
                    "agenda": [],
                    "discussions": [],
                    "decisions": [],
                    "action_items": []
                },
                required_fields=["title", "date", "attendees"]
            )
        }
    
    def generate_deliverable(self, task_id: str, task_type: str, task_data: Dict[str, Any],
                            created_by: str = "") -> Optional[Dict[str, Any]]:
        """生成任务成果物
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_data: 任务数据
            created_by: 创建者
            
        Returns:
            成果物数据字典
        """
        try:
            # 根据任务类型选择模板
            template = self._select_template(task_type)
            
            if not template:
                self.logger.error(f"未找到适合的模板: {task_type}")
                return None
            
            # 生成成果物内容
            content = self._generate_content(template, task_data)
            
            # 创建成果物记录
            deliverable = {
                "id": f"del_{task_id}_{int(time.time())}",
                "task_id": task_id,
                "name": self._generate_deliverable_name(task_type, task_data),
                "type": template.type,
                "content": json.dumps(content, ensure_ascii=False),
                "file_path": "",
                "version": 1,
                "created_at": time.time(),
                "updated_at": time.time(),
                "created_by": created_by,
                "metadata": json.dumps({
                    "template": template.type,
                    "task_type": task_type,
                    "generation_method": "auto"
                })
            }
            
            self.logger.info(f"成果物已生成: {deliverable['id']}")
            return deliverable
            
        except Exception as e:
            self.logger.error(f"生成成果物失败: {e}")
            return None
    
    def create_custom_deliverable(self, task_id: str, name: str, deliverable_type: str,
                                  content: Dict[str, Any], created_by: str = "") -> Optional[Dict[str, Any]]:
        """创建自定义成果物
        
        Args:
            task_id: 任务ID
            name: 成果物名称
            deliverable_type: 成果物类型
            content: 成果物内容
            created_by: 创建者
            
        Returns:
            成果物数据字典
        """
        try:
            deliverable = {
                "id": f"del_{task_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                "task_id": task_id,
                "name": name,
                "type": deliverable_type,
                "content": json.dumps(content, ensure_ascii=False),
                "file_path": "",
                "version": 1,
                "created_at": time.time(),
                "updated_at": time.time(),
                "created_by": created_by,
                "metadata": json.dumps({
                    "template": "custom",
                    "generation_method": "manual"
                })
            }
            
            self.logger.info(f"自定义成果物已创建: {deliverable['id']}")
            return deliverable
            
        except Exception as e:
            self.logger.error(f"创建自定义成果物失败: {e}")
            return None
    
    def update_deliverable_version(self, deliverable: Dict[str, Any], 
                                   new_content: Dict[str, Any]) -> Dict[str, Any]:
        """更新成果物版本
        
        Args:
            deliverable: 成果物记录
            new_content: 新内容
            
        Returns:
            更新后的成果物记录
        """
        try:
            deliverable["content"] = json.dumps(new_content, ensure_ascii=False)
            deliverable["version"] += 1
            deliverable["updated_at"] = time.time()
            
            self.logger.info(f"成果物版本已更新: {deliverable['id']} -> v{deliverable['version']}")
            return deliverable
            
        except Exception as e:
            self.logger.error(f"更新成果物版本失败: {e}")
            return deliverable
    
    def export_deliverable(self, deliverable: Dict[str, Any], format: str = "json") -> Optional[str]:
        """导出成果物
        
        Args:
            deliverable: 成果物记录
            format: 导出格式（json, markdown, txt）
            
        Returns:
            导出的内容字符串
        """
        try:
            content = json.loads(deliverable["content"])
            
            if format == "json":
                return json.dumps(content, indent=2, ensure_ascii=False)
            
            elif format == "markdown":
                return self._convert_to_markdown(deliverable, content)
            
            elif format == "txt":
                return self._convert_to_text(deliverable, content)
            
            else:
                self.logger.error(f"不支持的导出格式: {format}")
                return None
                
        except Exception as e:
            self.logger.error(f"导出成果物失败: {e}")
            return None
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """获取所有可用模板
        
        Returns:
            模板列表
        """
        templates = []
        
        for template in self.templates.values():
            templates.append({
                "type": template.type,
                "name": template.name,
                "description": template.description,
                "required_fields": template.required_fields
            })
        
        return templates
    
    def add_custom_template(self, template: DeliverableTemplate) -> bool:
        """添加自定义模板
        
        Args:
            template: 模板对象
            
        Returns:
            是否添加成功
        """
        try:
            self.templates[template.type] = template
            self.logger.info(f"自定义模板已添加: {template.type}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加自定义模板失败: {e}")
            return False
    
    def _select_template(self, task_type: str) -> Optional[DeliverableTemplate]:
        """选择适合的模板
        
        Args:
            task_type: 任务类型
            
        Returns:
            模板对象
        """
        # 任务类型到模板的映射
        type_mapping = {
            "analysis": "analysis_report",
            "planning": "project_plan",
            "design": "product_design",
            "development": "technical_document",
            "meeting": "meeting_minutes"
        }
        
        template_type = type_mapping.get(task_type.lower())
        
        if template_type and template_type in self.templates:
            return self.templates[template_type]
        
        # 默认使用分析报告模板
        return self.templates.get("analysis_report")
    
    def _generate_content(self, template: DeliverableTemplate, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成成果物内容
        
        Args:
            template: 模板对象
            task_data: 任务数据
            
        Returns:
            成果物内容字典
        """
        content = template.structure.copy()
        
        # 填充基本信息
        if "title" in content:
            content["title"] = task_data.get("name", "未命名任务")
        
        # 根据模板类型填充特定内容
        if template.type == "analysis_report":
            content = self._fill_analysis_report(content, task_data)
        elif template.type == "product_design":
            content = self._fill_product_design(content, task_data)
        elif template.type == "project_plan":
            content = self._fill_project_plan(content, task_data)
        elif template.type == "technical_document":
            content = self._fill_technical_document(content, task_data)
        elif template.type == "meeting_minutes":
            content = self._fill_meeting_minutes(content, task_data)
        
        return content
    
    def _fill_analysis_report(self, content: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """填充分析报告内容"""
        content["summary"] = f"本报告针对{task_data.get('name', '相关主题')}进行分析。"
        content["methodology"] = "采用系统化分析方法，结合数据收集和专家评估。"
        content["findings"] = [
            "发现1：需要进一步分析",
            "发现2：需要进一步验证"
        ]
        content["conclusions"] = "基于当前分析，建议进一步深入研究。"
        content["recommendations"] = [
            "建议1：进行更详细的数据收集",
            "建议2：咨询相关领域专家"
        ]
        return content
    
    def _fill_product_design(self, content: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """填充产品设计文档内容"""
        content["overview"] = f"本文档描述{task_data.get('name', '产品')}的设计方案。"
        content["requirements"] = [
            "需求1：功能需求",
            "需求2：性能需求"
        ]
        content["design_specifications"] = {
            "ui_design": "待详细设计",
            "ux_design": "待详细设计"
        }
        content["user_stories"] = [
            "作为用户，我希望...",
            "作为管理员，我希望..."
        ]
        return content
    
    def _fill_project_plan(self, content: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """填充项目计划内容"""
        content["objectives"] = [
            "目标1：完成主要功能",
            "目标2：确保质量标准"
        ]
        content["scope"] = "项目范围定义"
        content["deliverables"] = [
            "成果物1：设计文档",
            "成果物2：实现代码"
        ]
        content["timeline"] = {
            "phase1": "需求分析（1-2周）",
            "phase2": "设计阶段（2-3周）",
            "phase3": "实施阶段（4-6周）"
        }
        return content
    
    def _fill_technical_document(self, content: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """填充技术文档内容"""
        content["introduction"] = f"本文档描述{task_data.get('name', '系统')}的技术实现。"
        content["architecture"] = {
            "components": ["前端", "后端", "数据库"],
            "technologies": ["Python", "Flask", "SQLite"]
        }
        content["implementation"] = {
            "backend": "使用Python Flask框架",
            "frontend": "使用HTML/CSS/JavaScript"
        }
        return content
    
    def _fill_meeting_minutes(self, content: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """填充会议纪要内容"""
        content["date"] = datetime.now().strftime('%Y-%m-%d')
        content["attendees"] = ["参会人员1", "参会人员2"]
        content["agenda"] = [
            "议题1：项目进展",
            "议题2：问题讨论"
        ]
        content["discussions"] = [
            "讨论1：当前进展顺利",
            "讨论2：需要解决技术问题"
        ]
        content["decisions"] = [
            "决策1：继续推进项目",
            "决策2：安排技术评审"
        ]
        content["action_items"] = [
            "行动项1：完成任务A",
            "行动项2：准备材料B"
        ]
        return content
    
    def _generate_deliverable_name(self, task_type: str, task_data: Dict[str, Any]) -> str:
        """生成成果物名称
        
        Args:
            task_type: 任务类型
            task_data: 任务数据
            
        Returns:
            成果物名称
        """
        task_name = task_data.get("name", "任务")
        timestamp = datetime.now().strftime('%Y%m%d')
        
        name_mapping = {
            "analysis": f"{task_name}_分析报告_{timestamp}",
            "planning": f"{task_name}_项目计划_{timestamp}",
            "design": f"{task_name}_设计方案_{timestamp}",
            "development": f"{task_name}_技术文档_{timestamp}",
            "meeting": f"{task_name}_会议纪要_{timestamp}"
        }
        
        return name_mapping.get(task_type.lower(), f"{task_name}_成果物_{timestamp}")
    
    def _convert_to_markdown(self, deliverable: Dict[str, Any], content: Dict[str, Any]) -> str:
        """转换为Markdown格式
        
        Args:
            deliverable: 成果物记录
            content: 内容字典
            
        Returns:
            Markdown格式字符串
        """
        lines = [f"# {deliverable['name']}\n"]
        lines.append(f"**类型**: {deliverable['type']}\n")
        lines.append(f"**创建时间**: {datetime.fromtimestamp(deliverable['created_at']).strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**版本**: v{deliverable['version']}\n\n")
        
        for key, value in content.items():
            lines.append(f"## {key}\n\n")
            
            if isinstance(value, str):
                lines.append(f"{value}\n\n")
            elif isinstance(value, list):
                for item in value:
                    lines.append(f"- {item}\n")
                lines.append("\n")
            elif isinstance(value, dict):
                for k, v in value.items():
                    lines.append(f"**{k}**: {v}\n")
                lines.append("\n")
        
        return "".join(lines)
    
    def _convert_to_text(self, deliverable: Dict[str, Any], content: Dict[str, Any]) -> str:
        """转换为纯文本格式
        
        Args:
            deliverable: 成果物记录
            content: 内容字典
            
        Returns:
            纯文本格式字符串
        """
        lines = [f"成果物名称: {deliverable['name']}"]
        lines.append(f"类型: {deliverable['type']}")
        lines.append(f"创建时间: {datetime.fromtimestamp(deliverable['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"版本: v{deliverable['version']}")
        lines.append("\n" + "="*50 + "\n")
        
        for key, value in content.items():
            lines.append(f"\n{key.upper()}")
            lines.append("-" * len(key))
            
            if isinstance(value, str):
                lines.append(value)
            elif isinstance(value, list):
                for item in value:
                    lines.append(f"• {item}")
            elif isinstance(value, dict):
                for k, v in value.items():
                    lines.append(f"{k}: {v}")
        
        return "\n".join(lines)
