# OPC-Agents

**Version**: 2.0.0 (Refactored)

> **An intelligent work assistant for one-person companies. As simple as talking to a secretary, truly getting all the work done.**

## Core Philosophy

**OPC-Agents** is an intelligent work assistant system designed for **One-Person Companies** (OPC).

Through natural conversation with the **Executive Office**, you can:
- ✅ Delegate work, not create tasks
- ✅ Get results, not processes
- ✅ Enjoy service, not operate tools

**You're not operating a tool, you're delegating to a professional secretary!**

---

## 🎯 Core Value

### From "Tool" to "Assistant"

| Traditional Tools | OPC-Agents |
|---------|-----------|
| ❌ Command-based operation | ✅ Conversational interaction |
| ❌ Process-oriented | ✅ Result-oriented |
| ❌ Feature-stacking | ✅ Scenario-driven |
| ❌ Mechanical execution | ✅ Proactive service |
| ❌ Unclear delivery | ✅ Clear deliverables |

---

## 💼 Core Scenarios

### 1. Launch New Product

**You say**: "I want to launch a new product"

**Executive Office**:
```
Great! I'll immediately arrange the new product launch work.
Expected completion: 1 business day, including:
1. Market Research (2 hours) - 📊 Market Research Report
2. Product Design (3 hours) - 📋 Product Requirements Document
3. Marketing Plan (2 hours) - 📈 Marketing Strategy
4. Final Review (1 hour) - 📦 Complete Launch Plan

Shall we start now?
```

**Final Deliverables**:
```
📦 Work Results (4 items)
├─ 📊 Market Research Report
├─ 📋 Product Requirements Document
├─ 📈 Marketing Strategy
└─  New Product Launch Plan (Complete Version)
```

### 2. Write Report

**You say**: "Help me write a market analysis report"

**Executive Office**:
```
Received! I'll immediately arrange the report writing work.
Expected completion: 2-4 hours, including:
1. Data Collection (1 hour)
2. Data Analysis (1 hour)
3. Report Writing (1-2 hours)

Which aspects should I focus on?
```

**Final Deliverables**:
```
📦 Work Results
└─ 📄 Professional Analysis Report (with data charts, trend analysis, conclusions & recommendations)
```

### 3. Organize Meeting

**You say**: "Organize a project discussion meeting"

**Executive Office**:
```
Great! I'll arrange the meeting.
Expected completion: 30 minutes, including:
1. Time Coordination (15 minutes)
2. Send Invitations (5 minutes)
3. Material Preparation (30 minutes)

What's the meeting topic and who should attend?
```

**Final Deliverables**:
```
📦 Work Results
├─  Meeting Time Schedule
├─ 📧 Meeting Invitations (sent)
└─  Meeting Materials Package (agenda, background materials, discussion points)
```

---

## 🤖 Executive Office Persona

### Persona Characteristics

- **Name**: Executive Office Secretary
- **Role**: Your exclusive work assistant
- **Tone**: Professional yet warm
- **Style**: Proactive, meticulous, efficient
- **Principles**:
  1. Everything has an account - every task has a beginning and an end
  2. Proactive not passive - think ahead, report proactively
  3. Result-oriented - focus on delivery quality, not just process
  4. Simple and efficient - don't make you think, one-stop solution
  5. Continuous learning - remember your preferences, understand you better over time

### Dialogue Style

**Accepting Tasks**:
> "Great, I'll arrange it immediately! Expected completion in {duration}."

**Progress Reporting**:
> "Reporting to you: {task_name} current progress {progress}%, expected completion {eta}."

**Task Completion**:
> "Task completed! Here are the deliverables, please review."

**Encountering Issues**:
> "Encountered an issue requiring your decision: {issue}. My recommendation is {suggestion}."

**Proactive Reminders**:
> "Reminder: {task_name} deadline is {deadline}, current progress {progress}%."

---

## 🏷️ Tag-Based Management

### Flexible Tag System (Replacing Fixed Departments)

**4 Dimensions**:

1. **Task Type** (10 types)
   - 🔍 Research | 🎨 Design | 💻 Development | 📝 Writing
   - 📊 Analysis |  Testing | 👥 Meeting | 📄 Documentation
   - ✅ Review | 📅 Planning

2. **Priority** (4 levels)
   - 🔥 Urgent (2 hours)
   - ⭐ Important (24 hours)
   - 📌 Normal (3 business days)
   - 🐢 Low (1 week)

3. **Skills** (8 types)
   - 💬 Communication | ✍️ Writing | 🎨 Design
   - 👨‍💻 Coding | 🔬 Analysis | 📚 Research
   - 🎤 Presentation | 📊 Management

4. **Business Domain** (8 domains)
   - 📦 Product | 📢 Marketing | 💰 Sales
   - 👥 HR | 💵 Finance | 📈 Operations
   - 🛟 Support | 🎯 Strategy

### Intelligent Tag Recommendation

**You say**: "Write a market analysis report"

**System recommends**:
```
Task Type: 📝 Writing | 📊 Analysis
Priority: ⭐ Important
Skills: ✍️ Writing | 🔬 Analysis
Business Domain: 📢 Marketing
```

---

## 🎨 Interface Design

### Conversation Center

- **Personified Greeting**: "Hello! I'm the Executive Office Secretary, what work would you like to delegate to me today?"
- **Natural Dialogue Flow**: As simple as WeChat chat
- **Task Cards Embedded**: Task progress and results displayed in conversation
- **Real-time Feedback**: Progress updates, completion notifications

### Work Results Area

- **Card Display**: Icon classification, clear and beautiful
- **One-Click Operations**: View, download, share
- **Results Statistics**: X items completed
- **Auto-Archive**: Historical results traceable

### Responsive Design

- **Desktop**: Full features, multi-column layout
- **Tablet**: Sidebar collapsed
- **Mobile**: Single column layout, touch-friendly

---

## 🏗️ Technical Architecture

### Core Modules

```
OPC-Agents/
├── config/                     # Configuration modules
│   ├── president_office_persona.py  # Executive Office persona config
│   ├── task_tags.py                 # Tag system config
│   └── __init__.py
├── opc_manager/                # Core manager
│   ├── scenario_engine.py      # Scenario engine (new)
│   ├── opc_manager.py          # OPC manager
│   ├── task_manager.py         # Task management
│   └── workflow_engine.py      # Workflow engine
├── web_interface/              # Web interface
│   ├── app.py                  # Flask application
│   └── templates/              # HTML templates
│       └── index.html          # Main interface (with deliverables area)
├── tests/                      # Tests
│   ├── e2e/                    # End-to-end tests
│   │   └── test_scenario_workflows.py
│   └── unit/                   # Unit tests
└── docs/                       # Documentation
    ├── dialogue_experience_optimization.md
    └── ...
```

### Scenario Engine

```python
# 3 core scenarios
- launch_product    # New product launch (4-step workflow)
- write_report      # Report writing (3-step workflow)
- organize_meeting  # Meeting organization (3-step workflow)

# Intelligent matching
match_scenario(user_input) -> {
    matched: True/False,
    workflow_id: "launch_product",
    confidence: 0.95
}
```

### Workflow Engine

```python
# Workflow definition
workflow = {
    "id": "launch_product",
    "workflow": [
        {
            "step": 1,
            "name": "Market Research",
            "estimated_duration": "2 hours",
            "output": {
                "name": "Market Research Report",
                "format": "PDF/Word"
            }
        },
        # ... more steps
    ],
    "final_deliverable": {
        "title": "Complete New Product Launch Plan"
    }
}
```

---

## 🚀 Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure System

```bash
# Copy configuration template
cp config.toml.sample config.toml

# Edit configuration file, set API keys, etc.
```

### Start System

```bash
# Use startup script
./OPCstart.sh

# Or run directly
python web_interface/app.py
```

### Access Interface

Open browser and visit: `http://localhost:5009`

---

## ✅ Testing

### Run End-to-End Tests

```bash
# Test core scenario workflows
python -m pytest tests/e2e/test_scenario_workflows.py -v

# Run all tests
python -m pytest tests/ -v
```

### Test Coverage

- ✅ Scenario matching tests (12 test cases)
- ✅ Workflow structure tests
- ✅ Dependency relationship tests
- ✅ End-to-end process tests

---

## 📊 Performance Metrics

### Response Time

- Conversation response: < 500ms
- Scenario recognition: < 1s
- Task creation: < 2s

### User Satisfaction

- Conversation naturalness: > 4.5/5
- Result satisfaction: > 4.5/5
- Proactive service: > 4.5/5

### Task Completion Rate

- Scenario task completion: > 90%
- On-time delivery: > 85%
- User repurchase rate: > 80%

---

## 📝 Changelog

### v2.0.0 (Refactored) - 2026-04-07

**Core Improvements**:
- ✅ Redefined Executive Office persona design
- ✅ Implemented scenario-based workflows (3 core scenarios)
- ✅ Redesigned result delivery interface
- ✅ Simplified department management to tag system
- ✅ Optimized core conversation experience
- ✅ Removed WeChat integration (postponed)

**New Features**:
- 🎯 Scenario Engine: Intelligent understanding of user intent
- 🏷️ Tag System: Flexible task classification
- 📦 Deliverables Management: Clear work results
- 🤖 Personified Dialogue: Warm and professional secretary experience

**Technical Optimizations**:
- 🔒 Enhanced security (XSS/CSRF/CSP)
- ⚡ Performance optimization (lazy loading, event delegation)
- 🧪 Comprehensive testing (end-to-end test coverage)
- 📊 Frontend monitoring (performance metrics tracking)

---

## 🤝 Team Consensus

### What We Achieved

✅ **Return to Original Intention** - Focus on "one-person company" core needs  
✅ **Persona Design** - Executive Office like a real secretary  
✅ **Scenario-Driven** - Understand real work scenarios  
✅ **Result-Oriented** - Clear delivery of work results  
✅ **Simplified Architecture** - Remove unnecessary complexity  

### Core Value

**Enable one-person company employees to complete all the work they want through conversation with the Executive Office.**

No longer a cold task creation tool, but:
- ✅ A work partner who understands you
- ✅ A proactive work assistant
- ✅ A reliable work secretary

---

## 📖 Related Documentation

- [Dialogue Experience Optimization](docs/dialogue_experience_optimization.md)
- [Scenario Engine Design](docs/scenario_engine_design.md)
- [Tag System Description](docs/tag_system.md)
- [Test Report](docs/test_report.md)

---

## 🙏 Acknowledgments

Thanks to all team members who contributed to this project!

Special thanks to:
- UI/UX designer for critical suggestions
- Architect for in-depth review
- Test manager for strict quality control
- Critical reviewer for ruthless questioning

It's your strict requirements that made OPC-Agents 2.0 possible today!

---

**OPC-Agents** - Making one-person companies more efficient, easier, and smarter! 🚀
