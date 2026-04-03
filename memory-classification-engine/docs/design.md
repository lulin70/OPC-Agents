# 记忆分类引擎 - 详细设计文档

## 1. 系统架构设计

### 1.1 整体架构

记忆分类引擎采用模块化、分层架构设计，主要由以下组件组成：

```
┌─────────────────────┐
│     外部系统       │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│    API/SDK接口      │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│   核心引擎          │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│  多层判断管道        │
│ ┌─────────────────┐ │
│ │ 规则匹配层       │ │
│ ├─────────────────┤ │
│ │ 结构分析层       │ │
│ ├─────────────────┤ │
│ │ 语义推断层       │ │
│ └─────────────────┘ │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│  记忆管理           │
│ ┌─────────────────┐ │
│ │ 去重与冲突检测   │ │
│ ├─────────────────┤ │
│ │ 遗忘机制         │ │
│ └─────────────────┘ │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│  存储层            │
│ ┌─────────────────┐ │
│ │ 工作记忆         │ │
│ ├─────────────────┤ │
│ │ 程序性记忆       │ │
│ ├─────────────────┤ │
│ │ 情节记忆         │ │
│ ├─────────────────┤ │
│ │ 语义记忆         │ │
│ └─────────────────┘ │
└─────────────────────┘
```

### 1.2 核心组件说明

1. **API/SDK接口**：提供外部系统与记忆分类引擎的交互接口，支持Python SDK和REST API。

2. **核心引擎**：协调各模块工作，处理外部请求，是整个系统的中枢。

3. **多层判断管道**：
   - **规则匹配层**：基于正则表达式和关键词匹配，识别明确的用户信号。
   - **结构分析层**：分析对话的交互模式，识别重复提问、方案接受/拒绝等模式。
   - **语义推断层**：调用LLM进行语义分析，处理复杂的记忆识别。

4. **记忆管理**：
   - **去重与冲突检测**：避免重复记忆，处理记忆冲突。
   - **遗忘机制**：基于时间、频率和重要性的加权衰减算法。

5. **存储层**：
   - **工作记忆**：内存存储，会话结束后清除。
   - **程序性记忆**：基于文件系统的存储，适合用户偏好、行为规则。
   - **情节记忆**：基于SQLite的存储，适合决策记录、任务模式。
   - **语义记忆**：基于SQLite的存储，适合事实声明、关系信息。

## 2. 核心模块设计

### 2.1 核心引擎模块

#### 2.1.1 功能设计
- 初始化和配置管理
- 处理用户消息，协调多层判断管道
- 管理记忆的存储和检索
- 提供外部接口

#### 2.1.2 类设计

```python
class MemoryClassificationEngine:
    def __init__(self, config_path=None):
        # 初始化引擎，加载配置
        pass
    
    def process_message(self, message, context=None):
        # 处理用户消息，返回记忆分类结果
        pass
    
    def retrieve_memories(self, query, limit=5):
        # 根据查询检索相关记忆
        pass
    
    def manage_memory(self, action, memory_id, data=None):
        # 管理记忆（查看、编辑、删除）
        pass
    
    def get_stats(self):
        # 获取系统统计信息
        pass
```

### 2.2 多层判断管道模块

#### 2.2.1 规则匹配层

**功能**：基于规则配置识别明确的用户信号。

**设计**：
- 规则配置：YAML格式，支持正则表达式和关键词匹配
- 规则加载：从配置文件加载规则
- 规则匹配：对用户输入应用规则，识别记忆类型

**规则配置示例**：
```yaml
rules:
  - pattern: "记住(这个|这点|这条)"
    memory_type: user_preference
    tier: 2
    action: extract_following_content
  
  - pattern: "(不要|别|以后不)(用|写|做|说)"
    memory_type: user_preference
    tier: 2
    action: extract_following_content
  
  - pattern: "(不对|错了|不是|你搞错了|我说的是)"
    memory_type: correction
    tier: 3
    action: extract_surrounding_context
```

#### 2.2.2 结构分析层

**功能**：分析对话结构，识别模式。

**设计**：
- 对话状态跟踪：跟踪对话的状态和模式
- 重复检测：检测重复提问和任务模式
- 方案接受/拒绝识别：识别用户对方案的接受或拒绝

#### 2.2.3 语义推断层

**功能**：使用LLM进行语义分析，处理复杂的记忆识别。

**设计**：
- LLM调用：调用轻量级LLM进行语义分析
- 提示词设计：设计有效的提示词，指导LLM进行记忆分类
- 成本控制：限制LLM调用频率，缓存结果

**提示词示例**：
```
你是一个记忆分类器。分析以下对话片段，判断是否有值得长期记忆的信息。

记忆类型包括：
- user_preference: 用户表达的偏好或习惯
- fact_declaration: 用户陈述的客观事实
- decision: 达成的明确决定或结论
- relationship: 涉及人物、团队、组织之间的关系
- task_pattern: 反复出现的任务类型
- sentiment_marker: 用户对某话题的情感倾向
- correction: 用户对之前输出的纠正

如果对话中没有值得记忆的信息，返回空。

当前对话：
{conversation_snippet}

已知的用户记忆：
{existing_memory_summary}

请以JSON格式输出，包含以下字段：
- has_memory: boolean
- memory_type: string (枚举值)
- content: string (记忆内容，简洁准确)
- tier: int (2=程序性记忆, 3=情节记忆, 4=语义记忆)
- confidence: float (0.0-1.0)
- reasoning: string (简要判断理由)
```

### 2.3 记忆管理模块

#### 2.3.1 去重与冲突检测

**功能**：检测和处理记忆重复与冲突。

**设计**：
- 重复检测：基于内容相似度和记忆类型检测重复记忆
- 冲突检测：检测新记忆与旧记忆的冲突
- 冲突解决：提供基于时间戳和置信度的冲突解决机制

#### 2.3.2 遗忘机制

**功能**：基于时间、频率和重要性自动衰减和淘汰低价值记忆。

**设计**：
- 记忆权重计算：基于时间衰减、访问频率和置信度计算记忆权重
- 记忆归档：当记忆权重低于阈值时，将其标记为归档
- 记忆清理：定期清理归档的记忆

**权重计算公式**：
```
记忆权重 = confidence × recency_score × frequency_score

recency_score = exp(-λ × days_since_last_access)  # 指数衰减
frequency_score = log(1 + access_count)            # 对数增长，边际递减
```

### 2.4 存储层模块

#### 2.4.1 工作记忆

**功能**：存储当前会话的上下文信息。

**设计**：
- 内存存储：使用Python字典或队列存储
- 会话管理：会话结束后自动清除
- 大小限制：设置最大容量，避免内存占用过大

#### 2.4.2 程序性记忆

**功能**：存储用户偏好、行为规则等固定信息。

**设计**：
- 文件存储：使用YAML/JSON文件存储
- 层级加载：支持全局、项目级和局部级别的配置
- 格式设计：结构化格式，便于读取和修改

**存储格式示例**：
```yaml
user_preferences:
  - id: "pref_001"
    content: "使用双引号而不是单引号"
    created_at: "2026-04-03T10:00:00Z"
    updated_at: "2026-04-03T10:00:00Z"
    confidence: 1.0
    source: "rule:0"
```

#### 2.4.3 情节记忆

**功能**：存储决策记录、任务模式等时间相关信息。

**设计**：
- SQLite存储：使用SQLite数据库存储
- 表结构设计：包含记忆元数据和内容
- 检索优化：支持基于时间和内容的检索

**表结构设计**：
```sql
CREATE TABLE episodic_memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    context TEXT,
    status TEXT DEFAULT 'active'
);
```

#### 2.4.4 语义记忆

**功能**：存储事实声明、关系信息等结构化知识。

**设计**：
- SQLite存储：使用SQLite数据库存储
- 关系模型：使用实体-关系-属性模型
- 查询优化：支持复杂的关系查询

**表结构设计**：
```sql
CREATE TABLE semantic_entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE semantic_relationships (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confidence REAL NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES semantic_entities(id),
    FOREIGN KEY (object_id) REFERENCES semantic_entities(id)
);
```

## 3. 数据模型设计

### 3.1 记忆元数据模型

```json
{
  "id": "mem_20260403_001",
  "type": "user_preference",
  "tier": 2,
  "content": "使用双引号而不是单引号",
  "created_at": "2026-04-03T10:00:00Z",
  "updated_at": "2026-04-03T10:00:00Z",
  "last_accessed": "2026-04-03T10:30:00Z",
  "access_count": 5,
  "confidence": 1.0,
  "source": "rule:0",
  "context": "用户在讨论代码风格时提到",
  "status": "active"
}
```

### 3.2 记忆类型枚举

```python
MEMORY_TYPES = {
    "user_preference": "用户偏好",
    "correction": "纠正信号",
    "fact_declaration": "事实声明",
    "decision": "决策记录",
    "relationship": "关系信息",
    "task_pattern": "任务模式",
    "sentiment_marker": "情感标记"
}
```

### 3.3 记忆层级枚举

```python
MEMORY_TIERS = {
    1: "工作记忆",
    2: "程序性记忆",
    3: "情节记忆",
    4: "语义记忆"
}
```

## 4. API接口设计

### 4.1 Python SDK接口

```python
class MemoryClassificationEngine:
    def __init__(self, config_path=None):
        """初始化引擎"""
        pass
    
    def process_message(self, message, context=None):
        """处理用户消息，返回记忆分类结果"""
        pass
    
    def retrieve_memories(self, query, limit=5):
        """根据查询检索相关记忆"""
        pass
    
    def manage_memory(self, action, memory_id, data=None):
        """管理记忆（查看、编辑、删除）"""
        pass
    
    def get_stats(self):
        """获取系统统计信息"""
        pass
    
    def export_memories(self, format="json"):
        """导出记忆数据"""
        pass
    
    def import_memories(self, data, format="json"):
        """导入记忆数据"""
        pass
```

### 4.2 REST API接口

#### 4.2.1 处理消息
- **URL**: `/api/message`
- **Method**: POST
- **Request Body**:
  ```json
  {
    "message": "记住，我不喜欢在代码中使用破折号",
    "context": {}
  }
  ```
- **Response**:
  ```json
  {
    "matched": true,
    "memory_type": "user_preference",
    "tier": 2,
    "content": "不喜欢在代码中使用破折号",
    "confidence": 1.0,
    "source": "rule:0"
  }
  ```

#### 4.2.2 检索记忆
- **URL**: `/api/memories`
- **Method**: GET
- **Query Parameters**:
  - `query`: 检索查询
  - `limit`: 结果数量限制
- **Response**:
  ```json
  {
    "memories": [
      {
        "id": "mem_20260403_001",
        "type": "user_preference",
        "tier": 2,
        "content": "不喜欢在代码中使用破折号",
        "confidence": 1.0,
        "source": "rule:0"
      }
    ]
  }
  ```

#### 4.2.3 管理记忆
- **URL**: `/api/memories/{id}`
- **Method**: GET, PUT, DELETE
- **Request Body** (PUT):
  ```json
  {
    "content": "不喜欢在代码中使用破折号和分号",
    "confidence": 1.0
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "memory": {
      "id": "mem_20260403_001",
      "type": "user_preference",
      "tier": 2,
      "content": "不喜欢在代码中使用破折号和分号",
      "confidence": 1.0,
      "source": "rule:0"
    }
  }
  ```

## 5. 测试方案设计

### 5.1 单元测试

**测试目标**：验证各模块的功能正确性。

**测试内容**：
- 核心引擎初始化和配置
- 规则匹配层的规则加载和匹配
- 结构分析层的模式识别
- 语义推断层的LLM调用和结果解析
- 记忆管理的去重和冲突检测
- 遗忘机制的权重计算和记忆归档
- 存储层的读写操作

**测试工具**：
- pytest
- mock库（模拟LLM调用）

### 5.2 集成测试

**测试目标**：验证模块之间的集成是否正常。

**测试内容**：
- 完整的记忆分类流程
- 记忆存储和检索流程
- 记忆管理操作
- API接口调用

**测试工具**：
- pytest
- requests（测试REST API）

### 5.3 性能测试

**测试目标**：验证系统的性能和资源占用。

**测试内容**：
- 记忆分类响应时间
- 记忆检索响应时间
- 系统处理并发请求的能力
- 内存占用
- 存储占用

**测试工具**：
- pytest-benchmark
- timeit
- memory-profiler

### 5.4 用户验收测试

**测试目标**：验证系统是否满足用户需求。

**测试内容**：
- 记忆分类的准确性
- 记忆检索的相关性
- 记忆管理的易用性
- 系统的整体用户体验

**测试方法**：
- 准备测试用例
- 由用户代表执行测试
- 收集用户反馈
- 分析测试结果

## 6. 部署方案设计

### 6.1 部署环境

**本地部署**：
- Python 3.8+
- 依赖库：PyYAML, SQLite3, Flask（可选，用于REST API）

**容器部署**：
- Docker镜像
- Docker Compose配置

### 6.2 配置管理

**配置文件**：
- `config/config.yaml`：系统配置
- `config/rules.yaml`：规则配置

**环境变量**：
- `MCE_CONFIG_PATH`：配置文件路径
- `MCE_DATA_PATH`：数据存储路径
- `MCE_LLM_API_KEY`：LLM API密钥（可选）

### 6.3 部署步骤

**本地部署**：
1. 克隆代码库
2. 安装依赖：`pip install -r requirements.txt`
3. 配置规则：编辑 `config/rules.yaml`
4. 启动服务：`python -m memory_classification_engine`

**容器部署**：
1. 构建镜像：`docker build -t memory-classification-engine .`
2. 运行容器：`docker run -p 5000:5000 memory-classification-engine`

### 6.4 监控与维护

**监控**：
- 日志记录：系统运行日志
- 性能监控：响应时间、资源占用
- 错误监控：异常和错误记录

**维护**：
- 定期备份数据
- 定期清理归档记忆
- 定期更新规则配置

## 7. 安全性设计

### 7.1 数据安全

- **数据加密**：敏感记忆信息加密存储
- **访问控制**：基于角色的访问权限管理
- **数据最小化**：只存储必要的记忆信息
- **遗忘机制**：支持用户主动删除记忆
- **审计日志**：记录所有记忆访问和修改操作

### 7.2 API安全

- **认证**：API访问需要认证
- **授权**：基于角色的权限控制
- **输入验证**：验证用户输入，防止注入攻击
- **速率限制**：防止API滥用
- **HTTPS**：使用HTTPS保护传输数据

## 8. 扩展性设计

### 8.1 模块扩展

- **记忆类型扩展**：支持添加新的记忆类型
- **存储后端扩展**：支持添加新的存储后端
- **判断层扩展**：支持添加新的判断层

### 8.2 集成扩展

- **Agent框架集成**：支持与不同Agent框架集成
- **LLM集成**：支持与不同LLM集成
- **第三方服务集成**：支持与第三方服务集成

## 9. 技术风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| 语义推断层性能问题 | 响应时间过长，影响用户体验 | 优先使用轻量级模型，设置调用频率限制，实现缓存机制 |
| 存储容量增长过快 | 系统性能下降，存储成本增加 | 实现自动遗忘机制，定期清理低价值记忆，优化存储结构 |
| 记忆冲突处理复杂 | 系统行为不可预测，用户体验差 | 设计明确的冲突解决策略，提供用户干预机制，记录冲突历史 |
| 多语言支持难度 | 跨语言记忆一致性问题 | 采用基于语义的记忆表示，优先支持英文和中文，使用翻译API进行跨语言映射 |
| LLM依赖风险 | LLM服务不可用，系统功能受限 | 实现降级策略，当LLM不可用时，仅使用规则匹配和结构分析层 |

## 10. 结论

本详细设计文档提供了记忆分类引擎的完整技术实现方案，包括系统架构、核心模块设计、数据模型设计、API接口设计、测试方案设计、部署方案设计、安全性设计和扩展性设计。

该设计采用模块化、分层架构，确保系统的可扩展性和可维护性。同时，通过轻量级的技术选型，确保系统能够在资源受限的环境下正常运行。

本设计充分考虑了用户需求和技术挑战，提供了一个完整、实用的记忆分类引擎实现方案。