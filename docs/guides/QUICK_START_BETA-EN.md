# OPC-Agents Beta Quick Start Guide

> **Version**: v0.2.4
> **Updated**: 2026-05-16
> **Status**: Beta

---

**Languages**: [中文](QUICK_START_BETA.md) | **English** | [日本語](QUICK_START_BETA-JP.md)

---

## 🎯 Welcome, Beta Testers!

Thank you for participating in the OPC-Agents Beta test! This guide will help you get started quickly.

**Latest Updates (2026-05-17)**:
- ✅ **v0.2.0 FINAL**: Product Release Final — Unified settings (5-tab) + first-run onboarding (3-step) + data backup/restore (ZIP/JSON/CSV+SHA256) + friendly error handling (9 exceptions→friendly messages) + WeChat E2E integration + modular dashboard (3×3×6=9 combos) + tri-lingual i18n (zh/en/ja 58+ keys) + Skill Marketplace V2 (detail/filter/version pinning) + global search + Apple Shortcuts (5 actions) + API Key encryption (Fernet) + code modularization refactor (frontend 8 modules / backend 84 modules / 1126 tests / 39 test files)
- ✅ v0.1.9-delta: Real-run verification — Three-Sage LLM-driven + Skill Marketplace FastAPI + MCP transport + Plugin examples + Editor UI + Performance monitoring
- ✅ v0.1.9-gamma: Refactoring — Three-Sage integration + Skill Marketplace API + MCP protocol + Plugin system + Skill editor
- ✅ v0.1.9: End-to-end closed loop — auto-correction + multi-skill orchestration + task pause/resume + progress visualization + long session context
- ✅ v0.1.8: Core skill development — 6 skills upgraded from mock to real + search enhancement + LLM integration
- ✅ v0.1.7: Three-Sage Architecture — Strategist Brain + Executor Brain + Reflector Brain + Consensus Engine + Skill Registry + Tool Framework
- ✅ v0.1.6: First-time onboarding + Quality feedback + Deliverable search + Empty state examples
- ✅ v0.1.5: Multi-turn follow-up + Quality gate + Output redaction + Ollama support + Protocol degradation
- ✅ v0.1.2: Security hardening (XSS/Prompt injection) + Performance optimization + PyPI release

---

## 📦 Quick Install (5 Minutes)

### Option 1: pip Install (Simplest)

```bash
pip install opc-agents
opc-agents
```

> First-time setup requires API Key: create a `.env` file in your working directory with `MOKA_API_KEY=your-key`

### Option 2: Source Install (Customizable)

#### 1. Clone the Project

```bash
git clone https://github.com/lulin70/OPC-Agents.git
cd OPC-Agents
```

#### 2. Install Dependencies

**Option A: One-Click Install (Recommended)**
```bash
chmod +x install.sh start.sh
./install.sh
```

**Option B: Manual Install**
```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Configure API Key (Optional but Recommended)

```bash
# Copy config template
cp .env.example .env

# Edit .env file and fill in your API Key
# Supports any of the following:
# - MOKA_API_KEY (recommended, supports multiple models)
# - GLM_API_KEY (Zhipu AI)
# - OPENAI_API_KEY (OpenAI)
# - OLLAMA_BASE_URL (Ollama local models, e.g. http://localhost:11434)
# - OLLAMA_ENABLED=true (Enable Ollama, uses default URL if BASE_URL not set)
# - OLLAMA_MODEL=llama3 (Ollama model name, default llama3)
```

**No API Key?** No problem! The system will automatically fall back to template mode, which still works.

#### 4. Launch the System

```bash
./start.sh
```

Your browser will automatically open `http://localhost:8501`

---

## 🚀 Getting Started

### Typical Use Cases

#### Scenario 1: Information Collection
```
Input: "Collect the latest AI Agent trends for 2026"
Output: Real search results + structured research report (downloadable .md file)
```

#### Scenario 2: Plan Generation
```
Input: "Create a Q2 marketing plan"
Output: Complete execution plan with goals/timeline/resources/risks/acceptance criteria
```

#### Scenario 3: Data Analysis
```
Input: "Analyze my current business situation"
Output: SWOT analysis + specific action items
```

#### Scenario 4: Unified Settings Management (v0.2.0 New)
```
1. Click "⚙️ Settings" in sidebar or top navigation bar
2. 5 tabs available:
   - 🤖 LLM Config: Manage multiple API Keys, model selection, parameter tuning
   - 📧 SMTP Email: Configure mail server, sender info
   - 🔑 API Keys: View/manage all configured API Keys (encrypted storage)
   - 🛡️ Security: Data encryption, access control, audit log settings
   - 👤 Profile: Business type, preferences, language selection
3. All changes take effect immediately, no restart needed
```

#### Scenario 5: First-Run Onboarding
```
Auto-triggered 3-step wizard on first launch:
Step 1: 🎉 Welcome — Learn about OPC-Agents core capabilities
Step 2: 🔑 API Key Setup — Quick LLM service config (can skip)
Step 3: ✨ Feature Intro — Discover 21 built-in skills and key features
```

#### Scenario 6: Data Backup & Restore
```
Location: Settings → Data Backup tab
Export formats supported:
- ZIP archive (full backup with SHA256 verification)
- JSON format (data exchange)
- CSV format (finance/CRM data in spreadsheets)

Security features:
- Zip Slip path traversal protection
- Sensitive field auto-redaction
- Encrypted backup storage
```

#### Scenario 7: Internationalization (i18n)
```
3 languages with instant switching (no restart):
- 🇨🇳 中文 (zh_CN) — Default
- 🇺🇸 English (en_US)
- 🇯🇵 日本語 (ja_JP)

Switch via: Settings → Profile → Language Selection
Coverage: All UI text + error messages + skill descriptions
```

#### Scenario 8: Apple Shortcuts Integration
```
5 predefined shortcut actions via CLI:

# Quick task creation
opc-agents --shortcut quick_task --goal "Finish Q2 report"

# Query task status
opc-agents --shortcut query_status

# Create deliverable
opc-agents --shortcut create_deliverable --type report

# Record income
opc-agents --shortcut record_income --amount 5000 --source "Consulting"

# Generate daily report
opc-agents --shortcut daily_report
```

---

## ⚠️ Known Beta Limitations

### Current Version Limitations

1. **Search Functionality**
   - Relies on DuckDuckGo, may occasionally fail
   - Automatically falls back to knowledge base when unavailable
   - Does not affect basic usage

2. **LLM Functionality**
   - Requires API Key for AI-enhanced mode
   - Uses template mode without API Key (slightly lower quality but functional)

3. **Content Quality**
   - Generated content requires human review
   - Recommended to use as a first draft, then adjust based on actual needs

### Startup Messages

You may see the following messages at startup — **this is normal**:

- API Key detected → Shows "🤖 AI-Enhanced Mode"
- No API Key detected → Shows "📝 Template Mode" (fully functional, slightly lower content quality)

---

## 🐛 Having Issues?

### Common Questions

#### Q1: Startup fails with missing dependencies
```bash
# Solution: Reinstall dependencies
pip install --upgrade -r requirements.txt
```

#### Q2: Search functionality not working
```
Cause: Network issue or DuckDuckGo rate limiting
Impact: System automatically falls back to knowledge base
Suggestion: Try again later, or check network connection
```

#### Q3: LLM initialization fails
```
Cause: No API Key configured
Impact: Uses template mode (slightly lower quality)
Suggestion: Configure API Key in .env file
```

#### Q4: Generated content is too generic
```
Cause: Search failed + LLM not configured
Suggestion:
1. Configure API Key to enable AI enhancement
2. Provide more specific input information
3. Manually adjust the generated content
```

### Reporting Bugs

If you encounter other issues, please report them through:

1. **GitHub Issues**: https://github.com/lulin70/OPC-Agents/issues
2. **GitHub Discussions**: https://github.com/lulin70/OPC-Agents/discussions

**Please include in your report**:
- Operating system version
- Python version
- Error message screenshot
- Steps to reproduce

---

## 📊 Beta Testing Focus Areas

We especially want you to test the following areas:

### 1. Core Functionality Testing

- [ ] Information Collection: Does search return relevant results?
- [ ] Plan Generation: Are the generated plans usable?
- [ ] Data Analysis: Are the analysis results valuable?
- [ ] File Download: Do .md files download correctly?

### 2. User Experience Testing

- [ ] Is the startup process smooth?
- [ ] Is the interface easy to use?
- [ ] Are error messages clear?
- [ ] Is the response speed acceptable?

### 3. Content Quality Testing

- [ ] Does generated content contain placeholders?
- [ ] Does the content meet your needs?
- [ ] Does it require significant modification to be usable?

### 4. Stability Testing

- [ ] Is continuous usage stable?
- [ ] Do any crashes occur?
- [ ] Are memory/CPU usage levels normal?

---

## 💡 Usage Tips

### Tip 1: Provide Specific Information

❌ Poor input:
```
"Write a plan"
```

✅ Good input:
```
"Create a Q2 marketing plan for an AI writing assistant,
goal is to increase MAU from 5000 to 10000, budget 50,000 CNY"
```

### Tip 2: Execute Step by Step

For complex tasks, break them down:

```
Step 1: "Collect competitor information for AI writing assistants"
Step 2: "Based on the above, create a differentiation strategy"
Step 3: "Create a detailed execution plan"
```

### Tip 3: Use the Download Feature

Every piece of generated content can be downloaded as a .md file:
- Click the "📥 Download Deliverable" button
- Continue refining in your local editor
- Easier version management

---

## 🎁 Beta Test Feedback

Thank you for your participation! We value your feedback:

**How to provide feedback**:
1. Complete the test checklist above
2. Submit at least 1 valuable bug or suggestion
3. Report via GitHub Issues or WeChat Group

---

## 📞 Contact Us

- **Project Homepage**: https://github.com/lulin70/OPC-Agents
- **Documentation**: https://github.com/lulin70/OPC-Agents/tree/main/docs
- **Discussions**: https://github.com/lulin70/OPC-Agents/discussions

---

## 🗺️ Roadmap

### Near-term Updates (1-2 weeks)

- [ ] Improve search stability
- [ ] Optimize LLM generation quality
- [ ] Add more scenario templates
- [ ] Improve error messages

### Mid-term Plans (1-2 months)

- [ ] Support more LLM backends
- [ ] Add team collaboration features
- [ ] Mobile adaptation
- [ ] Open API interface

---

**Thank you again for participating in the Beta test! Your feedback is crucial to us.** 🙏

---

*Last updated: 2026-05-17*
*Version: v0.2.0 FINAL*
