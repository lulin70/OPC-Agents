# OPC-Agents 安全设计文档

**日期**: 2026-05-07
**版本**: v1.0
**对应需求**: REQ-SEC-001/002/003/004
**对应PRD**: PRD_V3.md 第六章 6.1/6.6
**对应架构**: AGENT_BRAIN_DESIGN_CONSENSUS.md v2.0 第五章
**安全专家**: ✅ 已审核

---

## 1. 威胁建模

### 1.1 STRIDE分析

| 威胁类型 | 威胁描述 | 影响组件 | 风险等级 | 对应需求 |
|---------|---------|---------|---------|---------|
| **Spoofing（欺骗）** | 伪造Agent身份执行恶意操作 | ExecutorBrain | 高 | REQ-SEC-001 |
| **Tampering（篡改）** | 通过命令注入篡改系统文件 | ToolSystem | 严重 | REQ-SEC-001 |
| **Repudiation（抵赖）** | 恶意操作无审计记录 | ToolSystem | 中 | REQ-SEC-003 |
| **Information Disclosure（信息泄露）** | 通过路径穿越读取敏感文件 | ToolSystem | 严重 | REQ-SEC-002 |
| **Denial of Service（拒绝服务）** | 超长输入导致系统崩溃 | 所有组件 | 中 | REQ-SEC-004 |
| **Elevation of Privilege（权限提升）** | 通过Agent执行提权命令 | ToolSystem | 严重 | REQ-SEC-001 |

### 1.2 攻击面分析

```
┌─────────────────────────────────────────────────────────────┐
│                       攻击面                                 │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ 用户输入  │    │ 工具调用  │    │ 文件操作  │              │
│  │ (自然语言)│    │ (命令执行)│    │ (读写)   │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                     │
│       ↓               ↓               ↓                     │
│  ┌─────────────────────────────────────────────┐           │
│  │              安全防护层                       │           │
│  │  InputValidator + CommandWhitelist + PathCheck│           │
│  └─────────────────────────────────────────────┘           │
│       │               │               │                     │
│       ↓               ↓               ↓                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ 策略脑   │    │ 执行脑   │    │ 工具系统  │              │
│  └──────────┘    └──────────┘    └──────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 攻击树

**目标：通过Agent执行任意系统命令**

```
执行任意命令
├── 通过工具系统命令执行
│   ├── 注入shell元字符 (; | & $ `)
│   ├── 使用路径形式绕过白名单 (/bin/rm)
│   ├── 命令替换 ($() / ``)
│   └── 环境变量注入 ($HOME/.bashrc)
├── 通过文件操作
│   ├── 写入恶意脚本到可执行目录
│   ├── 修改配置文件
│   └── 替换可执行文件
└── 通过超长输入
    ├── 缓冲区溢出
    └── 资源耗尽DoS
```

---

## 2. 安全控制设计

### 2.1 命令执行安全（REQ-SEC-001）

**控制措施**：

| 层级 | 控制措施 | 实现方式 |
|------|---------|---------|
| L1-输入验证 | 长度限制 | 命令参数≤1000字符 |
| L2-解析安全 | 参数化执行 | `shlex.split()` + `shell=False` |
| L3-白名单 | 命令白名单 | 只允许预定义的安全命令 |
| L4-路径检查 | basename提取 | `os.path.basename(cmd)` 防止路径绕过 |
| L5-审计 | 操作日志 | 所有命令执行/拒绝记录到审计日志 |
| L6-超时 | 执行超时 | `asyncio.wait_for(30s)` |

**命令白名单定义**：

```python
ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "echo", "pwd", "whoami",
    "date", "df", "du", "find", "grep", "sort", "uniq", "curl", "ping",
}
```

**白名单原则**：
- 只包含只读/信息类命令
- 不包含任何修改/删除/网络服务类命令
- 新增命令需安全专家审核

### 2.2 文件访问安全（REQ-SEC-002）

**控制措施**：

| 层级 | 控制措施 | 实现方式 |
|------|---------|---------|
| L1-路径规范化 | 绝对路径解析 | `os.path.abspath()` |
| L2-穿越检测 | ".."检测 | `normpath().split(os.sep)` 检查 |
| L3-目录限制 | 允许目录前缀匹配 | `configure_allowed_dirs()` |
| L4-审计 | 操作日志 | 所有文件操作/拒绝记录 |
| L5-长度限制 | 路径长度限制 | ≤500字符 |

**默认允许目录**：

```python
_ALLOWED_BASE_DIRS = []  # 默认为空，必须显式配置

# 使用方式
configure_allowed_dirs(["/path/to/workspace/deliverables"])
```

### 2.3 审计日志（REQ-SEC-003）

**日志格式**：

```json
{
    "timestamp": "2026-05-07T10:30:00.000Z",
    "event_type": "COMMAND_REJECTED",
    "severity": "HIGH",
    "details": {
        "input": "ls; rm -rf /",
        "reason": "命令不被允许: rm",
        "source_ip": null,
        "task_id": "task-123"
    }
}
```

**事件类型**：

| 事件类型 | 严重度 | 说明 |
|---------|--------|------|
| COMMAND_EXECUTED | INFO | 命令成功执行 |
| COMMAND_REJECTED | HIGH | 命令被白名单拒绝 |
| PATH_ACCESS_GRANTED | INFO | 文件访问被允许 |
| PATH_REJECTED | HIGH | 文件路径被拒绝 |
| INPUT_LENGTH_EXCEEDED | MEDIUM | 输入超出长度限制 |

### 2.4 输入长度限制（REQ-SEC-004）

| 输入类型 | 最大长度 | 超出处理 |
|---------|---------|---------|
| 用户输入 | 10000字符 | 返回错误 |
| 命令参数 | 1000字符 | 返回错误 |
| 文件路径 | 500字符 | 返回错误 |
| 技能参数 | 5000字符 | 返回错误 |

---

## 3. 安全编码规范

### 3.1 禁止模式

| 禁止模式 | 原因 | 替代方案 |
|---------|------|---------|
| `subprocess.run(cmd, shell=True)` | 命令注入 | `create_subprocess_exec(*shlex.split(cmd))` |
| `open(user_input_path)` | 路径穿越 | `_validate_path(user_input_path)` 后再open |
| `eval(user_input)` | 代码注入 | `ast.literal_eval()` 或JSON解析 |
| `os.system(cmd)` | 命令注入 | `asyncio.create_subprocess_exec()` |
| `time.sleep()` in async | 阻塞事件循环 | `asyncio.sleep()` |

### 3.2 必须模式

| 必须模式 | 适用场景 |
|---------|---------|
| `isinstance(data, dict)` before `.get()` | 所有dict字段访问 |
| `shlex.split()` for command parsing | 所有命令解析 |
| `os.path.abspath()` for path resolution | 所有文件路径处理 |
| `asyncio.wait_for(timeout)` | 所有外部调用 |

---

## 4. 安全测试验证

> 详细测试用例见 TEST_PLAN_PHASE1.md 3.9节

| 安全需求 | 测试用例数 | 覆盖攻击向量 |
|---------|-----------|-------------|
| REQ-SEC-001 | 8 | 分号/管道/反引号/$()/路径绕过/白名单正常/审计 |
| REQ-SEC-002 | 6 | 相对穿越/绝对越权/SSH/正常/动态配置/审计 |
| REQ-SEC-004 | 4 | 用户输入/命令参数/文件路径/正常长度 |

---

**文档状态**: ✅ 安全专家完成 | ⏳ 待全员审核
