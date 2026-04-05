# 总裁办任务分解流程详解

**日期**: 2026-04-04  
**版本**: 3.0.0

---

## 📊 完整流程图

```
用户提交需求
    ↓
1️⃣ 总裁办接收请求
    ↓
2️⃣ 意图判断（闲聊/搜索/任务/追问）
    ↓
3️⃣ 三贤者决策（战略/执行/创新）
    ↓
4️⃣ 任务分解（动态分解）
    ↓
5️⃣ 能力检测（主动发现缺口）
    ↓
6️⃣ 用户确认计划
    ↓
7️⃣ DAG 依赖调度
    ↓
8️⃣ 智能角色匹配
    ↓
9️⃣ Agent 协同执行
    ↓
🔟 完成自动校验
    ↓
1️⃣1️⃣ 经验沉淀
```

---

## 🎯 详细步骤说明

### 步骤 1：总裁办接收请求

**入口**: Web 界面 → `/api/chat/<chat_id>/message`

**路由**: [`web_interface/routes/executive_office.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/web_interface/routes/executive_office.py)

```python
@executive_bp.route('/api/chat/<int:chat_id>/message', methods=['POST'])
def send_message(chat_id):
    data = request.json
    user_message = data['message']
    
    # 调用总裁办处理
    response = opc_manager.process_user_request(user_message, chat_id)
    
    return jsonify({'response': response})
```

---

### 步骤 2：意图判断

**文件**: [`opc_manager/core.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_manager/core.py)

**4 种意图**:

```python
def determine_intent(self, user_input: str) -> str:
    """判断用户意图"""
    prompt = f"""判断用户意图（闲聊/搜索/任务/追问）:
    输入：{user_input}
    
    只输出：chat/search/task/followup
    """
    intent = self.communication_manager.model_manager.generate_response(prompt)
    return intent.strip()
```

**意图分类**:
- **chat（闲聊）**: "你好"、"今天天气不错"
- **search（搜索）**: "帮我查一下..."、"搜索..."
- **task（任务）**: "我需要..."、"帮我做..."
- **followup（追问）**: "那..."、"然后呢..."、"为什么..."

---

### 步骤 3：三贤者决策

**文件**: [`opc_manager/three_sages.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_manager/three_sages.py)

**三视角评估**:

```python
def three_sages_decision(self, task: str) -> Dict:
    """三贤者决策系统"""
    
    # 1. 战略贤者（长期影响/风险/资源）
    strategic = self.model_manager.generate_response(f"""
    从战略角度评估任务：{task}
    - 长期影响
    - 风险评估
    - 资源需求
    """)
    
    # 2. 执行贤者（具体步骤/时间/负责人）
    execution = self.model_manager.generate_response(f"""
    从执行角度评估任务：{task}
    - 具体步骤
    - 时间规划
    - 负责人
    """)
    
    # 3. 创新贤者（替代方案/创新点/改进）
    innovation = self.model_manager.generate_response(f"""
    从创新角度评估任务：{task}
    - 替代方案
    - 创新点
    - 改进建议
    """)
    
    # 4. 综合三贤者意见，生成执行计划
    synthesis = self.model_manager.generate_response(f"""
    综合三贤者意见:
    战略：{strategic}
    执行：{execution}
    创新：{innovation}
    
    生成执行步骤（JSON 格式）:
    {{
        "execution_steps": [
            {{
                "step": 1,
                "task": "任务名",
                "department": "部门",
                "description": "描述",
                "deliverable": "产出物",
                "depends_on": [],
                "required_skills": [],
                "acceptance_criteria": []
            }}
        ],
        "monitoring_plan": [
            {{
                "checkpoint": "检查点",
                "trigger": "触发条件"
            }}
        ]
    }}
    """)
    
    return json.loads(synthesis)
```

**输出**:
```json
{
  "execution_steps": [
    {
      "step": 1,
      "task": "市场分析",
      "department": "marketing",
      "description": "调研目标市场",
      "deliverable": "市场分析报告.md",
      "depends_on": [],
      "required_skills": ["市场调研", "数据分析"],
      "acceptance_criteria": ["包含市场规模", "包含竞品分析"]
    }
  ],
  "monitoring_plan": [...]
}
```

---

### 步骤 4：任务分解（核心）

**文件**: [`opc_manager/core.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_manager/core.py#L280-L360)

**方法**: `decompose_task(task, synthesis, user_request)`

**分解逻辑**:

```python
def decompose_task(self, task: str, synthesis: Dict = None, user_request: str = None):
    """分解任务并检测能力缺口"""
    
    # 1. 如果三贤者已提供执行步骤，直接使用
    if synthesis and synthesis.get('execution_steps'):
        result = {
            "execution_steps": synthesis['execution_steps'],
            "monitoring_plan": synthesis.get('monitoring_plan', [])
        }
    else:
        # 2. 否则调用模型动态分解
        prompt = f"""
        请将以下任务分解为执行步骤，严格按 JSON 格式输出：
        任务：{task}
        
        {{
            "execution_steps": [
                {{
                    "step": 1,
                    "task": "任务名",
                    "department": "部门名 (engineering/design/marketing 等)",
                    "description": "具体描述",
                    "deliverable": "预期产出物"
                }}
            ],
            "monitoring_plan": [...]
        }}
        
        只输出 JSON。
        """
        response = self.model_manager.generate_response(prompt)
        result = json.loads(response)
    
    # 3. 检测能力缺口（新增）
    if user_request and hasattr(self, 'capability_discovery'):
        capability_result = self.detect_capability_gaps(user_request, context=task)
        result['capability_gaps'] = capability_result['gaps']
        result['recommendations'] = capability_result['recommendations']
        result['action_required'] = capability_result['action_required']
    
    return result
```

**分解原则**:
1. **原子性**: 每个步骤是独立的、可执行的
2. **依赖性**: 明确步骤之间的依赖关系（DAG）
3. **可交付**: 每个步骤有明确的产出物
4. **可验收**: 每个步骤有验收标准

---

### 步骤 5：能力检测（主动发现缺口）

**文件**: [`opc_hr/capability_discovery.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_hr/capability_discovery.py)

**检测流程**:

```python
def detect_capability_gaps(self, user_request: str, context: str = ""):
    """检测能力缺口并生成推荐"""
    
    # 1. 分析需求，提取关键词
    keywords = self.analyze_user_request(user_request)
    # 输出：['pdf', 'document', 'analyze']
    
    # 2. 检测能力缺口
    gaps = self.detect_capability_gap(keywords, context)
    # 输出：[CapabilityGap(skill_name='pdf', priority=7)]
    
    # 3. 搜索替代技能（双源搜索）
    all_candidates = []
    for gap in gaps:
        # ClawHub 搜索
        clawhub_skills = self.clawhub.execute('search_packages', query=gap.skill_name)
        # MCP GitHub 搜索
        mcp_skills = self.clawhub.search_skills(gap.skill_name)
        all_candidates.extend(clawhub_skills + mcp_skills)
    
    # 4. 评估候选（5 维度评分）
    best = self.evaluate_and_test(all_candidates, gap)
    # 评分：名称 40 + 分类 20 + 评分 20 + 下载量 10 + 安全 10 = 100
    
    # 5. 生成推荐
    recommendation = self.recommend_to_user(best, gap, user)
    # 输出：推荐理由 + 好处 + 风险
    
    return {
        'gaps': gaps,
        'recommendations': [recommendation],
        'action_required': True
    }
```

**触发时机**:
- ✅ 任务分解时（主动检测）
- ✅ 执行失败时（被动触发）

---

### 步骤 6：用户确认计划

**界面**: 总裁办对话窗口

**展示内容**:
```
📋 任务分解计划

任务：分析 PDF 文档并提取关键信息

执行步骤：
1️⃣ 市场分析（Marketing Dept, 30 分钟）
   产出：市场分析报告.md
   
2️⃣ 竞品分析（Marketing Dept, 20 分钟）
   产出：竞品分析.md
   依赖：步骤 1
   
3️⃣ 产品定位（Three Sages, 15 分钟）
   产出：产品定位报告.md
   依赖：步骤 1,2

⚠️ 能力缺口检测
检测到缺少 PDF 处理技能

推荐安装：PDF Processor
- 评分：4.5/5.0
- 下载量：15000+
- 安全性：✅ 通过扫描

[确认计划并安装] [修改计划] [取消]
```

---

### 步骤 7：DAG 依赖调度

**文件**: [`opc_manager/dag_scheduler.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_manager/dag_scheduler.py)

**调度流程**:

```python
def build_dag(self, execution_steps: List[Dict]) -> DAG:
    """构建 DAG 图"""
    dag = DAG()
    
    for step in execution_steps:
        dag.add_node(step['step'], step)
        for dep in step.get('depends_on', []):
            dag.add_edge(dep, step['step'])
    
    # 检测循环
    if not dag.is_dag():
        raise ValueError("检测到循环依赖")
    
    return dag

def get_ready_tasks(self, dag: DAG, completed: Set[int]) -> List[int]:
    """获取当前可执行的任务（依赖已满足）"""
    ready = []
    for node_id in dag.nodes():
        if node_id not in completed:
            deps = dag.predecessors(node_id)
            if all(dep in completed for dep in deps):
                ready.append(node_id)
    return ready
```

**执行顺序**:
```
步骤 1（无依赖）→ 立即执行
步骤 2（依赖 1）→ 等待步骤 1 完成
步骤 3（依赖 1,2）→ 等待步骤 1,2 完成
步骤 4（依赖 3）→ 等待步骤 3 完成
```

---

### 步骤 8：智能角色匹配

**文件**: [`opc_hr/role_matcher.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_hr/role_matcher.py)

**三层匹配策略**:

```python
def match(self, task: str, department: str) -> List[Agent]:
    """为任务匹配最合适的 Agent"""
    
    # 1. 历史表现匹配（30%）
    historical_score = self._match_historical(task, department)
    
    # 2. 技能匹配（40%）
    skill_score = self._match_skills(task)
    
    # 3. 关键词匹配（30%）
    keyword_score = self._match_keywords(task, department)
    
    # 综合评分
    total_score = (
        historical_score * 0.3 +
        skill_score * 0.4 +
        keyword_score * 0.3
    )
    
    return sorted(agents, key=lambda x: total_score, reverse=True)
```

**示例**:
```
任务："设计产品 Logo"
部门：design

匹配结果:
1. designer_agent (95 分)
   - 历史表现：30/30（成功完成 10 个设计任务）
   - 技能匹配：40/40（擅长 Logo 设计）
   - 关键词匹配：25/30（"design" 匹配）

2. creative_agent (82 分)
   - 历史表现：25/30
   - 技能匹配：35/40
   - 关键词匹配：22/30
```

---

### 步骤 9：Agent 协同执行

**文件**: [`opc_manager/task_executor.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_manager/task_executor.py)

**执行流程**:

```python
def execute_task(self, task_data: Dict):
    """执行单个任务"""
    
    # 1. 准备上下文
    context = {
        'user_request': task_data['user_request'],
        'three_sages_assessment': task_data['assessment'],
        'execution_plan': task_data['plan'],
        'previous_artifacts': task_data['previous_outputs']  # 前序 Agent 产出物
    }
    
    # 2. 调用 Agent
    agent = task_data['agent']
    prompt = self._build_prompt(agent, context)
    output = self.model_manager.generate_response(prompt)
    
    # 3. 保存产出物
    output_file = f"{agent}_output.md"
    log_file = f"{agent}.log"
    self._save_artifacts(output, output_file, log_file)
    
    # 4. 自动重试（失败时）
    if self._check_failure(output):
        retry_count = task_data.get('_retry_count', 0)
        if retry_count < max_retries:
            return self._retry(task_data, retry_count + 1)
    
    return output
```

**上下文传递**:
```
Agent 1 执行 → 产出物 A
  ↓
Agent 2 执行 → 获取产出物 A（实际内容，非路径）
  ↓
Agent 3 执行 → 获取产出物 A + B
```

---

### 步骤 10：完成自动校验

**文件**: [`opc_manager/completion_checker.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_manager/completion_checker.py)

**4 项检查**:

```python
def check_completion(self, task: Task) -> bool:
    """自动校验任务是否真正完成"""
    
    # 1. 产出物存在
    if not os.path.exists(task.deliverable):
        return False
    
    # 2. 产出物非空
    if os.path.getsize(task.deliverable) == 0:
        return False
    
    # 3. 验收标准满足
    criteria_met = self._check_criteria(task)
    if not criteria_met:
        return False
    
    # 4. GLM 质量评估
    quality_score = self.model_manager.generate_response(f"""
    评估产出物质量：
    任务：{task.name}
    产出物：{task.deliverable}
    验收标准：{task.acceptance_criteria}
    
    评分（0-100）：
    """)
    
    return int(quality_score) >= 60
```

---

### 步骤 11：经验沉淀

**文件**: [`opc_manager/context_manager.py`](file:///Users/lin/Documents/trae_projects/OPC-Agents/opc_manager/context_manager.py)

**双向同步**:

```python
def sync_task_to_global(self, task_context: TaskContext):
    """任务完成时沉淀经验到全局上下文"""
    
    # 1. 提取经验教训 → 经验库
    lesson = self._extract_lesson(task_context)
    self.global_context.experiences.append(lesson)
    
    # 2. 提取新知识 → 知识库
    knowledge = self._extract_knowledge(task_context.artifacts)
    self.global_context.knowledge.append(knowledge)
    
    # 3. 更新用户画像
    self.global_context.update_user_profile(task_context)
    
    # 4. 容量控制
    self.global_context.prune()  # LRU 淘汰
```

**效果**:
- ✅ 系统越用越聪明
- ✅ 后续任务自动复用经验
- ✅ 形成知识积累

---

## 🎯 总结

### 任务分解的核心逻辑

1. **三贤者决策** - 战略/执行/创新三视角评估
2. **动态分解** - 基于评估结果生成执行步骤
3. **能力检测** - 主动发现能力缺口并推荐
4. **DAG 调度** - 按依赖关系有序执行
5. **智能匹配** - 为任务找到最合适的 Agent
6. **上下文传递** - 前序产出物传递给后续 Agent
7. **自动校验** - 确保产出物质量
8. **经验沉淀** - 系统越用越聪明

### 关键特性

- ✅ **主动学习** - 检测能力缺口并推荐安装
- ✅ **依赖管理** - DAG 调度确保顺序
- ✅ **质量保证** - 4 项自动校验
- ✅ **断点恢复** - Checkpoint 保存进度
- ✅ **智能匹配** - 3 层匹配策略
- ✅ **经验积累** - 双层上下文管理

---

**文档版本**: 3.0.0  
**最后更新**: 2026-04-04  
**维护者**: OPC-Agents 产品团队
