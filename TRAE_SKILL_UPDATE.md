# OPC-Agents TRAE 技能更新指南

## 概述

本指南提供了如何将 TRAE 技能从 trae-agency 更新为 opc-agents 的详细步骤。

## 手动更新步骤

由于系统权限限制，需要手动更新 TRAE 技能目录：

### 1. 打开 TRAE 技能目录

```bash
# 打开技能目录
open ~/.trae/skills/
```

### 2. 重命名技能目录

将 `trae-agency` 目录重命名为 `opc-agents`：

### 3. 更新技能文件

将以下文件复制到 `opc-agents` 目录：

- `OPC-Agents/opc_skill.py` → `~/.trae/skills/opc-agents/agency_skill.py`
- `OPC-Agents/SKILL.md` (需要创建) → `~/.trae/skills/opc-agents/SKILL.md`

### 4. 更新 SKILL.md 文件

创建新的 SKILL.md 文件，内容如下：

```markdown
# OPC-Agents Skill

AI-powered agency system for One Person Company (OPC), integrated with TRAE.

## Commands

- 查看所有部门: 列出所有可用的部门及其代理数量
- 查看部门 [部门名称]: 查看指定部门的代理列表
- 安排任务 [部门] [任务描述] --agent [代理名称]: 分配任务给指定代理
- 创建项目 [项目名称] [任务1] [任务2]...: 创建包含多个任务的项目

## Configuration

- **Name**: opc-agents
- **Version**: 1.0.0
- **Description**: AI-powered agency system for One Person Company
- **Author**: OPC Team
```

### 5. 更新技能实现文件

将 `opc_skill.py` 的内容复制到 `~/.trae/skills/opc-agents/agency_skill.py`，并确保以下内容正确：

1. 导入路径正确指向 OPC-Agents 目录
2. 所有类名和引用都已更新为 OPCManager

### 6. 重启 TRAE

重启 TRAE 应用以加载更新后的技能。

## 验证更新

在 TRAE 对话界面中测试以下命令：

```
TRAEE, 查看所有部门
```

如果系统返回部门列表，则更新成功。

## 故障排除

### 技能未生效

1. 检查技能文件是否在正确目录
2. 确保文件权限正确（可读）
3. 重启 TRAE 应用
4. 检查 TRAE 设置中是否启用了技能功能

### 路径错误

确保 `opc_skill.py` 中的路径设置正确：

```python
# 确保路径指向正确的 OPC-Agents 目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trae_projects" / "OPC-Agents"))
```

## 联系支持

如果遇到任何问题，请联系 OPC 团队获取支持。