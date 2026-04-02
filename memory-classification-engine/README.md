# Memory Classification Engine

> 一个轻量级的Agent侧记忆分类引擎，实时判断对话中哪些内容值得记忆，以什么形式存储，存入哪个记忆层级。

## 项目背景

当前AI Agent的记忆管理存在一个核心问题：**什么内容值得被记住？**

大多数现有方案采用"全量摘要"策略，在对话结束后对整段对话做摘要存档。这导致：
- 记忆库中充满低价值噪音，检索时信噪比极低
- 无法区分不同类型的信息（偏好、事实、决策、关系）
- 遗忘和更新机制无法建立在无分类的记忆之上

本项目要解决的问题是：**在Agent侧实现一个轻量级的记忆分类引擎，实时判断对话中哪些内容值得记忆，以什么形式存储，存入哪个记忆层级。**

## 核心功能

### 1. 记忆分类
- **用户偏好** (`user_preference`)：用户明确表达的喜好、习惯、风格要求
- **纠正信号** (`correction`)：用户纠正AI的判断或输出
- **事实声明** (`fact_declaration`)：用户陈述的关于自身或业务的事实
- **决策记录** (`decision`)：对话中达成的明确结论或选择
- **关系信息** (`relationship`)：涉及人物、团队、组织之间的关系
- **任务模式** (`task_pattern`)：反复出现的任务类型及其处理方式
- **情感标记** (`sentiment_marker`)：用户对某话题的明确情感倾向

### 2. 记忆层级
- **Tier 1 - 工作记忆**：当前会话的上下文窗口，由LLM原生管理
- **Tier 2 - 程序性记忆**：用户偏好、行为规则、工作习惯，以系统提示词或配置文件形式加载
- **Tier 3 - 情节记忆**：决策记录、任务模式、重要对话摘要，存入向量数据库
- **Tier 4 - 语义记忆**：事实声明、关系信息、领域知识，存入知识图谱或关系型数据库

### 3. 三层判断管道
- **Layer 1: 规则匹配层**：基于正则表达式和关键词匹配，零成本，高准确率
- **Layer 2: 结构分析层**：分析对话的交互模式，轻量级，不依赖语义理解
- **Layer 3: 语义推断层**：调用LLM做语义分析，高成本，高覆盖率

### 4. 记忆管理
- **写入流程**：去重检查 → 冲突处理 → 写入对应层级存储
- **遗忘机制**：基于访问频率和时间的加权衰减
- **检索策略**：根据对话内容从不同层级检索相关记忆
- **注入格式**：结构化记忆注入到系统提示词

## 技术架构

```
对话内容
  │
  ▼
┌─────────────────────┐
│ Layer 1: 规则匹配层  │  ← 确定性规则，零成本，高准确率
└─────────┬───────────┘
          │ 未匹配的内容
          ▼
┌─────────────────────┐
│ Layer 2: 结构分析层  │  ← 对话结构模式识别，轻量级
└─────────┬───────────┘
          │ 未匹配的内容
          ▼
┌─────────────────────┐
│ Layer 3: 语义推断层  │  ← LLM判断，高成本，高覆盖率
└─────────┬───────────┘
          │
          ▼
   记忆写入决策
          │
          ▼
┌─────────────────────┐
│  去重与冲突检测    │
└─────────┬───────────┘
          │
          ├── 重复 → 更新已有记忆
          │
          ├── 冲突 → 标记为待确认
          │
          └── 新记忆 → 写入对应Tier
                          │
                          ├── Tier 2 → 配置文件/系统提示词
                          ├── Tier 3 → 向量数据库
                          └── Tier 4 → 知识图谱
```

## 技术选型

| 组件 | 建议方案 | 备选方案 |
|------|---------|---------|
| 规则引擎 | YAML配置 + 正则表达式 | JSON Schema |
| 对话状态跟踪 | 内存状态机 | Redis |
| 向量数据库（Tier 3） | ChromaDB（轻量本地） | Qdrant, Milvus |
| 知识图谱（Tier 4） | Neo4j | NetworkX（轻量级，适合起步） |
| 配置存储（Tier 2） | YAML/JSON文件 | SQLite |
| 语义分类（Layer 3） | 小模型API调用 | 本地小模型（Ollama） |
| Agent框架适配 | 设计为独立模块，提供SDK | 优先适配ClaudeCode、WorkBuddy |

## 项目里程碑

### Phase 1: 最小可用版本（MVP）
- 实现Layer 1规则匹配层
- 实现Tier 2程序性记忆的读写
- 以ClaudeCode的CLAUDE.md格式作为初始存储格式
- 提供3-5条默认规则

### Phase 2: 结构分析
- 实现Layer 2结构分析层
- 实现重复检测和模式识别
- 实现Tier 3向量数据库存储和检索
- 实现去重和冲突检测

### Phase 3: 语义推断
- 实现Layer 3语义推断层
- 设计并调优分类Prompt
- 实现成本控制机制

### Phase 4: 遗忘与进化
- 实现基于衰减的遗忘机制
- 实现记忆压缩（细节→模式）
- 实现用户记忆审阅界面（CLI）

### Phase 5: 生态扩展
- 支持多种Agent框架（ClaudeCode、Cursor、WorkBuddy等）
- 实现企业级的多用户记忆共享和权限管理
- 开放记忆导入/导出格式标准

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/memory-classification-engine.git
cd memory-classification-engine

# 安装依赖
pip install -r requirements.txt
```

### 基本使用

```python
from memory_classification_engine import MemoryClassificationEngine

# 初始化引擎
engine = MemoryClassificationEngine()

# 处理用户消息
user_message = "记住，我不喜欢在代码中使用破折号"
result = engine.process_message(user_message)
print(result)
# 输出: {"matched": true, "memory_type": "user_preference", "tier": 2, "content": "不喜欢在代码中使用破折号", "confidence": 1.0, "source": "rule:0"}

# 检索记忆
memories = engine.retrieve_memories("代码风格")
print(memories)
```

## 项目结构

```
memory-classification-engine/
├── src/
│   ├── memory_classification_engine/
│   │   ├── __init__.py
│   │   ├── engine.py          # 核心引擎
│   │   ├── layers/
│   │   │   ├── rule_matcher.py    # 规则匹配层
│   │   │   ├── pattern_analyzer.py # 结构分析层
│   │   │   └── semantic_classifier.py # 语义推断层
│   │   ├── storage/
│   │   │   ├── tier2.py        # 程序性记忆存储
│   │   │   ├── tier3.py        # 情节记忆存储
│   │   │   └── tier4.py        # 语义记忆存储
│   │   └── utils/
│   │       ├── config.py       # 配置管理
│   │       └── helpers.py      # 辅助函数
├── config/
│   └── rules.yaml              # 规则配置文件
├── tests/
│   ├── test_engine.py
│   ├── test_layers.py
│   └── test_storage.py
├── examples/
│   ├── basic_usage.py
│   └── agent_integration.py
├── requirements.txt
└── README.md
```

## 贡献指南

我们欢迎各种形式的贡献，包括但不限于：

- 报告bug和提出功能请求
- 提交代码改进和修复
- 完善文档
- 参与讨论和提供建议

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 文件了解详细的贡献流程。

## 许可证

本项目采用 [MIT License](LICENSE)。

## 与现有方案的对比

| 维度 | Mem0 | MemGPT | ClaudeCode | 本项目 |
|------|------|--------|-----------|--------|
| 记忆分类 | 有（基础） | 无 | 无（隐式按文件层级） | 有（7种类型，3层判断管道） |
| 写入判断 | 每次对话后全量提取 | 基于上下文窗口管理 | 手动/Hooks | 事件驱动，实时分类 |
| 记忆层级 | 单层（向量库） | 两层（内存+硬盘） | 单层（文件） | 四层（工作/程序性/情节/语义） |
| 遗忘机制 | 无 | 有（上下文淘汰） | 无 | 有（加权衰减+语义压缩） |
| 存储方式 | 向量数据库 | 虚拟内存抽象 | 文件系统 | 多存储后端（文件+向量+图谱） |
| Agent无关性 | 是（SDK） | 否（自有Agent） | 否（自有Agent） | 是（独立模块+SDK） |

## 开放问题

1. **记忆冲突的解决策略**：当新记忆与旧记忆矛盾时，是覆盖还是并存？是否需要用户确认？
2. **跨语言记忆一致性**：同一偏好用中文和英文分别表达时，如何识别为同一条记忆？
3. **记忆隐私边界**：在多Agent协作场景下，哪些记忆可以共享，哪些必须隔离？
4. **记忆质量的评估指标**：如何衡量一个记忆系统"记对了多少、记错了多少"？
5. **LLM侧记忆的可能性**：KV Cache持久化在工程上何时可行？Fine-tune个人记忆模型的成本何时降到可接受范围？

## 联系方式

- 项目主页：https://github.com/yourusername/memory-classification-engine
- 问题反馈：https://github.com/yourusername/memory-classification-engine/issues
- 讨论社区：https://github.com/yourusername/memory-classification-engine/discussions