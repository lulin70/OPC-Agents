# OPC-Agents Beta Quick Start Guide

> **Version**: v0.1.5  
> **Updated**: 2026-05-03  
> **Status**: Beta

---

**Languages**: [中文](QUICK_START_BETA.md) | **English** | [日本語](QUICK_START_BETA-JP.md)

---

## 🎯 Welcome, Beta Testers!

Thank you for participating in the OPC-Agents Beta test! This guide will help you get started quickly.

**Latest Updates (2026-04-28)**:
- ✅ Security hardening: XSS fixes, Prompt injection defense, API Key masking
- ✅ Performance optimization: Singleton pattern, thread safety, Token savings
- ✅ PyPI release: `pip install opc-agents` now available
- ✅ Fixed LLM init / search deps / scenario path / context pollution issues
- ✅ System is now more stable and reliable

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

*Last updated: 2026-05-03*  
*Version: v0.1.5*
