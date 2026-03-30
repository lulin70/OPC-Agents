#!/usr/bin/env python3
"""
MCPIntegration模块 - GitHub连接层

通过MCP协议连接GitHub，搜索和获取Agent定义、Skill定义。
为人事部提供外部Agent/Skill市场的搜索和导入能力。
"""

import json
import os
import re
import logging
import requests
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional


class MCPGitHubClient:
    """GitHub API客户端，用于搜索和获取Agent/Skill资源"""

    GITHUB_API = "https://api.github.com"
    RAW_CONTENT_URL = "https://raw.githubusercontent.com"

    def __init__(self, github_token: Optional[str] = None):
        self.logger = logging.getLogger('OPC-Agents.MCPGitHub')
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "OPC-Agents-MCP/1.0"
        })
        if github_token:
            self.session.headers["Authorization"] = f"token {github_token}"
            self.authenticated = True
        else:
            self.authenticated = False
            self.logger.warning("未配置GitHub Token，API请求频率受限（60次/小时）")

    def search_repositories(self, query: str, sort: str = "stars",
                            per_page: int = 10, page: int = 1) -> Dict[str, Any]:
        """搜索GitHub仓库"""
        try:
            params = {
                "q": query,
                "sort": sort,
                "order": "desc",
                "per_page": min(per_page, 100),
                "page": page
            }
            resp = self.session.get(f"{self.GITHUB_API}/search/repositories", params=params)
            resp.raise_for_status()
            data = resp.json()
            self.logger.info(f"GitHub仓库搜索 '{query}': 找到 {data.get('total_count', 0)} 个仓库")
            return data
        except Exception as e:
            self.logger.error(f"搜索GitHub仓库失败: {e}")
            return {"total_count": 0, "items": []}

    def search_code(self, query: str, sort: str = "indexed",
                    per_page: int = 10, page: int = 1) -> Dict[str, Any]:
        """搜索GitHub代码"""
        try:
            params = {
                "q": query,
                "sort": sort,
                "order": "desc",
                "per_page": min(per_page, 100),
                "page": page
            }
            resp = self.session.get(f"{self.GITHUB_API}/search/code", params=params)
            resp.raise_for_status()
            data = resp.json()
            self.logger.info(f"GitHub代码搜索 '{query}': 找到 {data.get('total_count', 0)} 个结果")
            return data
        except Exception as e:
            self.logger.error(f"搜索GitHub代码失败: {e}")
            return {"total_count": 0, "items": []}

    def get_file_content(self, owner: str, repo: str, path: str,
                         branch: str = "main") -> Optional[str]:
        """获取仓库中指定文件的内容"""
        try:
            url = f"{self.GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
            params = {"ref": branch}
            resp = self.session.get(url, params=params)
            if resp.status_code == 404:
                resp = self.session.get(url, params={"ref": "master"})
            resp.raise_for_status()
            data = resp.json()
            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            return data.get("content", "")
        except Exception as e:
            self.logger.error(f"获取文件内容失败 {owner}/{repo}/{path}: {e}")
            return None

    def get_repository_info(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """获取仓库详细信息"""
        try:
            resp = self.session.get(f"{self.GITHUB_API}/repos/{owner}/{repo}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"获取仓库信息失败 {owner}/{repo}: {e}")
            return None

    def get_rate_limit(self) -> Dict[str, Any]:
        """获取API速率限制"""
        try:
            resp = self.session.get(f"{self.GITHUB_API}/rate_limit")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}


class MCPIntegration:
    """MCP集成类 - 连接GitHub搜索Agent和Skill"""

    def __init__(self, github_token: Optional[str] = None,
                 agent_sources: Optional[List[Dict[str, str]]] = None,
                 skill_sources: Optional[List[Dict[str, str]]] = None):
        self.logger = logging.getLogger('OPC-Agents.MCPIntegration')
        self.github = MCPGitHubClient(github_token)
        self.agent_cache: Dict[str, Dict] = {}
        self.skill_cache: Dict[str, Dict] = {}
        self.import_history: List[Dict] = []
        self.verification_history: List[Dict] = []

        self.agent_sources = agent_sources or [
            {
                "owner": "elizaOS",
                "repo": "eliza",
                "path": "characters",
                "type": "agent",
                "description": "ElizaOS AI Agent框架"
            },
            {
                "owner": "microsoft",
                "repo": "autogen",
                "path": "python/packages/autogen-agentchat",
                "type": "agent",
                "description": "Microsoft AutoGen Agent框架"
            },
            {
                "owner": "langchain-ai",
                "repo": "langchain",
                "path": "libs/langchain/langchain/agents",
                "type": "agent",
                "description": "LangChain Agent工具"
            },
            {
                "owner": "crewAIInc",
                "repo": "crewAI",
                "path": "crewai/agent",
                "type": "agent",
                "description": "CrewAI Agent框架"
            }
        ]

        self.skill_sources = skill_sources or [
            {
                "owner": "mcp-marketplace",
                "repo": "awesome-mcp-servers",
                "path": "",
                "type": "skill",
                "description": "MCP Server市场"
            },
            {
                "owner": "modelcontextprotocol",
                "repo": "servers",
                "path": "src",
                "type": "skill",
                "description": "官方MCP Server集合"
            }
        ]

        self.logger.info(f"MCPIntegration初始化完成, Agent源: {len(self.agent_sources)}, Skill源: {len(self.skill_sources)}")

    def search_agents(self, query: str, department: Optional[str] = None,
                      limit: int = 10) -> List[Dict[str, Any]]:
        """搜索GitHub上的Agent定义"""
        results = []

        github_queries = [f"{query} agent"]
        if department:
            github_queries.append(f"{query} {department} agent")

        seen_repos = set()
        for q in github_queries:
            data = self.github.search_repositories(q, per_page=limit)
            for item in data.get("items", []):
                full_name = item["full_name"]
                if full_name in seen_repos:
                    continue
                seen_repos.add(full_name)

                agent_info = {
                    "source": "github",
                    "repo_full_name": full_name,
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "url": item["html_url"],
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "language": item.get("language", ""),
                    "updated_at": item.get("updated_at", ""),
                    "topics": item.get("topics", []),
                    "match_score": self._calculate_match_score(item, query, department)
                }
                results.append(agent_info)
                self.agent_cache[full_name] = agent_info

        results.sort(key=lambda x: x["match_score"], reverse=True)
        self.logger.info(f"搜索Agent '{query}': 找到 {len(results)} 个结果")
        return results[:limit]

    def search_skills(self, query: str, category: Optional[str] = None,
                      limit: int = 10) -> List[Dict[str, Any]]:
        """搜索GitHub上的Skill/MCP Server定义"""
        results = []

        github_queries = [f"{query} MCP server"]
        if category:
            github_queries.append(f"{query} {category} tool")
        github_queries.append(f"{query} skill plugin")

        seen_repos = set()
        for q in github_queries:
            data = self.github.search_repositories(q, per_page=limit)
            for item in data.get("items", []):
                full_name = item["full_name"]
                if full_name in seen_repos:
                    continue
                seen_repos.add(full_name)

                skill_info = {
                    "source": "github",
                    "repo_full_name": full_name,
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "url": item["html_url"],
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "language": item.get("language", ""),
                    "updated_at": item.get("updated_at", ""),
                    "topics": item.get("topics", []),
                    "match_score": self._calculate_match_score(item, query, category)
                }
                results.append(skill_info)
                self.skill_cache[full_name] = skill_info

        results.sort(key=lambda x: x["match_score"], reverse=True)
        self.logger.info(f"搜索Skill '{query}': 找到 {len(results)} 个结果")
        return results[:limit]

    def fetch_agent_details(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """获取Agent仓库的详细信息，尝试解析Agent定义"""
        try:
            repo_info = self.github.get_repository_info(*repo_full_name.split("/"))
            if not repo_info:
                return None

            details = {
                "source": "github",
                "repo_full_name": repo_full_name,
                "name": repo_info["name"],
                "full_name": repo_info["full_name"],
                "description": repo_info.get("description", ""),
                "url": repo_info["html_url"],
                "homepage": repo_info.get("homepage", ""),
                "stars": repo_info.get("stargazers_count", 0),
                "forks": repo_info.get("forks_count", 0),
                "language": repo_info.get("language", ""),
                "license": repo_info.get("license", {}).get("name", "未知") if repo_info.get("license") else "未知",
                "topics": repo_info.get("topics", []),
                "created_at": repo_info.get("created_at", ""),
                "updated_at": repo_info.get("updated_at", ""),
                "default_branch": repo_info.get("default_branch", "main"),
                "readme": None,
                "agent_definitions": [],
                "capabilities": []
            }

            readme_content = self.github.get_file_content(
                *repo_full_name.split("/"), "README.md", details["default_branch"]
            )
            if readme_content:
                details["readme"] = readme_content[:3000]
                details["capabilities"] = self._extract_capabilities_from_readme(readme_content)

            for source in self.agent_sources:
                if source["repo"] == repo_full_name.split("/")[1] and source["owner"] == repo_full_name.split("/")[0]:
                    if source["path"]:
                        agent_defs = self._scan_agent_definitions(
                            source["owner"], source["repo"], source["path"], details["default_branch"]
                        )
                        details["agent_definitions"] = agent_defs
                    break

            self.agent_cache[repo_full_name] = details
            self.logger.info(f"获取Agent详情成功: {repo_full_name}")
            return details
        except Exception as e:
            self.logger.error(f"获取Agent详情失败: {e}")
            return None

    def fetch_skill_details(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """获取Skill/MCP Server仓库的详细信息"""
        try:
            repo_info = self.github.get_repository_info(*repo_full_name.split("/"))
            if not repo_info:
                return None

            details = {
                "source": "github",
                "repo_full_name": repo_full_name,
                "name": repo_info["name"],
                "full_name": repo_info["full_name"],
                "description": repo_info.get("description", ""),
                "url": repo_info["html_url"],
                "homepage": repo_info.get("homepage", ""),
                "stars": repo_info.get("stargazers_count", 0),
                "forks": repo_info.get("forks_count", 0),
                "language": repo_info.get("language", ""),
                "license": repo_info.get("license", {}).get("name", "未知") if repo_info.get("license") else "未知",
                "topics": repo_info.get("topics", []),
                "created_at": repo_info.get("created_at", ""),
                "updated_at": repo_info.get("updated_at", ""),
                "default_branch": repo_info.get("default_branch", "main"),
                "readme": None,
                "skill_config": None,
                "tools": []
            }

            readme_content = self.github.get_file_content(
                *repo_full_name.split("/"), "README.md", details["default_branch"]
            )
            if readme_content:
                details["readme"] = readme_content[:3000]
                details["tools"] = self._extract_tools_from_readme(readme_content)

            for config_file in ["package.json", "pyproject.toml", "setup.py", "Cargo.toml"]:
                config_content = self.github.get_file_content(
                    *repo_full_name.split("/"), config_file, details["default_branch"]
                )
                if config_content:
                    details["skill_config"] = {
                        "file": config_file,
                        "content": config_content[:2000]
                    }
                    break

            self.skill_cache[repo_full_name] = details
            self.logger.info(f"获取Skill详情成功: {repo_full_name}")
            return details
        except Exception as e:
            self.logger.error(f"获取Skill详情失败: {e}")
            return None

    def import_agent(self, repo_full_name: str, target_department: Optional[str] = None) -> Dict[str, Any]:
        """从GitHub导入Agent到系统"""
        try:
            details = self.fetch_agent_details(repo_full_name)
            if not details:
                return {"success": False, "error": f"无法获取仓库信息: {repo_full_name}"}

            verification = self._verify_resource(details, "agent")
            if not verification["verified"]:
                return {
                    "success": False,
                    "error": "Agent验证未通过",
                    "verification": verification
                }

            agent_name = details["name"]
            agent_data = {
                "name": agent_name,
                "department": target_department or self._guess_department(details),
                "source": "github",
                "source_repo": repo_full_name,
                "frontmatter": {
                    "name": agent_name.replace("-", " ").title(),
                    "description": details["description"],
                    "color": "blue",
                    "imported_from": repo_full_name,
                    "imported_at": datetime.now().isoformat(),
                    "stars": details["stars"],
                    "license": details["license"]
                },
                "identity": details.get("readme", "")[:500] if details.get("readme") else "",
                "mission": "",
                "deliverables": "",
                "workflow": "",
                "metrics": "",
                "capabilities": details.get("capabilities", [])
            }

            record = {
                "type": "agent",
                "name": agent_name,
                "repo": repo_full_name,
                "imported_at": datetime.now().isoformat(),
                "verification": verification
            }
            self.import_history.append(record)

            self.logger.info(f"导入Agent成功: {agent_name} <- {repo_full_name}")
            return {
                "success": True,
                "agent_data": agent_data,
                "verification": verification
            }
        except Exception as e:
            self.logger.error(f"导入Agent失败: {e}")
            return {"success": False, "error": str(e)}

    def import_skill(self, repo_full_name: str) -> Dict[str, Any]:
        """从GitHub导入Skill/MCP Server到系统"""
        try:
            details = self.fetch_skill_details(repo_full_name)
            if not details:
                return {"success": False, "error": f"无法获取仓库信息: {repo_full_name}"}

            verification = self._verify_resource(details, "skill")
            if not verification["verified"]:
                return {
                    "success": False,
                    "error": "Skill验证未通过",
                    "verification": verification
                }

            skill_name = details["name"]
            skill_data = {
                "name": skill_name,
                "source": "github",
                "source_repo": repo_full_name,
                "description": details["description"],
                "tools": details.get("tools", []),
                "language": details["language"],
                "license": details["license"],
                "stars": details["stars"],
                "url": details["url"],
                "config": details.get("skill_config"),
                "imported_at": datetime.now().isoformat()
            }

            record = {
                "type": "skill",
                "name": skill_name,
                "repo": repo_full_name,
                "imported_at": datetime.now().isoformat(),
                "verification": verification
            }
            self.import_history.append(record)

            self.logger.info(f"导入Skill成功: {skill_name} <- {repo_full_name}")
            return {
                "success": True,
                "skill_data": skill_data,
                "verification": verification
            }
        except Exception as e:
            self.logger.error(f"导入Skill失败: {e}")
            return {"success": False, "error": str(e)}

    def verify_skill(self, skill_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证Skill的安全性和可靠性"""
        return self._verify_resource(skill_data, "skill")

    def _verify_resource(self, data: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        """验证资源的安全性和可靠性"""
        result = {
            "resource_type": resource_type,
            "name": data.get("name", "unknown"),
            "verified": False,
            "security_score": 0.0,
            "reliability_score": 0.0,
            "issues": [],
            "recommendations": []
        }

        stars = data.get("stars", 0)
        forks = data.get("forks", 0)
        has_license = data.get("license", "未知") != "未知"
        has_description = bool(data.get("description", ""))
        language = data.get("language", "")

        security_score = 0.5
        if has_license:
            security_score += 0.2
        else:
            result["issues"].append("无明确许可证")
        if stars >= 100:
            security_score += 0.15
        elif stars >= 10:
            security_score += 0.1
        if forks >= 50:
            security_score += 0.1
        elif forks >= 5:
            security_score += 0.05
        if language in ["Python", "TypeScript", "JavaScript"]:
            security_score += 0.05
        result["security_score"] = min(1.0, security_score)

        reliability_score = 0.4
        if has_description:
            reliability_score += 0.1
        else:
            result["issues"].append("缺少描述信息")
        if stars >= 50:
            reliability_score += 0.2
        elif stars >= 10:
            reliability_score += 0.1
        if forks >= 20:
            reliability_score += 0.15
        elif forks >= 5:
            reliability_score += 0.1
        if data.get("readme"):
            reliability_score += 0.1
        else:
            result["issues"].append("缺少README文档")
        if data.get("topics"):
            reliability_score += 0.05
        result["reliability_score"] = min(1.0, reliability_score)

        result["verified"] = result["security_score"] >= 0.6 and result["reliability_score"] >= 0.5

        if not result["verified"]:
            result["recommendations"].append("建议选择star数更多、有明确许可证的仓库")
        if not has_description:
            result["recommendations"].append("建议优先选择有详细描述的仓库")

        self.verification_history.append({
            "resource_type": resource_type,
            "name": data.get("name"),
            "timestamp": datetime.now().isoformat(),
            "result": result
        })

        return result

    def _calculate_match_score(self, item: Dict, query: str,
                               category: Optional[str] = None) -> float:
        """计算搜索结果匹配度"""
        score = 0.0
        name = item.get("name", "").lower()
        description = (item.get("description", "") or "").lower()
        topics = [t.lower() for t in item.get("topics", [])]

        query_lower = query.lower()
        if query_lower in name:
            score += 0.4
        if query_lower in description:
            score += 0.2
        for topic in topics:
            if query_lower in topic:
                score += 0.1

        if category:
            cat_lower = category.lower()
            if cat_lower in name:
                score += 0.3
            if cat_lower in description:
                score += 0.15
            for topic in topics:
                if cat_lower in topic:
                    score += 0.1

        stars = item.get("stargazers_count", 0)
        if stars >= 1000:
            score += 0.1
        elif stars >= 100:
            score += 0.05

        return min(1.0, score)

    def _extract_capabilities_from_readme(self, readme: str) -> List[str]:
        """从README中提取Agent能力"""
        capabilities = []
        patterns = [
            r'(?:capabilities?|features?|功能|能力)[:\s]*\n((?:[-*]\s*[^\n]+\n?)+)',
            r'(?:what can|支持|can\s+do)[:\s]*\n((?:[-*]\s*[^\n]+\n?)+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, readme, re.IGNORECASE)
            for match in matches:
                items = re.findall(r'[-*]\s*(.+)', match)
                capabilities.extend([item.strip() for item in items[:10]])
            if capabilities:
                break

        if not capabilities:
            lines = readme.split("\n")[:50]
            for line in lines:
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    item = line[2:].strip()
                    if 5 < len(item) < 100:
                        capabilities.append(item)
                if len(capabilities) >= 5:
                    break

        return capabilities[:10]

    def _extract_tools_from_readme(self, readme: str) -> List[str]:
        """从README中提取MCP工具列表"""
        tools = []
        patterns = [
            r'(?:tools?|工具|resources?|resources)[:\s]*\n((?:[-*]\s*[^\n]+\n?)+)',
            r'(?:available tools?|可用工具)[:\s]*\n((?:[-*]\s*[^\n]+\n?)+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, readme, re.IGNORECASE)
            for match in matches:
                items = re.findall(r'[-*]\s*(.+)', match)
                tools.extend([item.strip() for item in items[:10]])
            if tools:
                break
        return tools[:10]

    def _scan_agent_definitions(self, owner: str, repo: str,
                                 path: str, branch: str) -> List[Dict[str, Any]]:
        """扫描仓库中的Agent定义文件"""
        definitions = []
        try:
            content = self.github.get_file_content(owner, repo, path, branch)
            if not content:
                return definitions

            if content.strip().startswith("["):
                try:
                    agents = json.loads(content)
                    for agent in agents[:5]:
                        definitions.append({
                            "name": agent.get("name", "unknown"),
                            "department": agent.get("department", "unknown"),
                            "description": agent.get("frontmatter", {}).get("description", ""),
                            "source_file": f"{owner}/{repo}/{path}"
                        })
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            self.logger.debug(f"扫描Agent定义失败 {owner}/{repo}/{path}: {e}")

        return definitions

    def _guess_department(self, details: Dict[str, Any]) -> str:
        """根据仓库信息猜测所属部门"""
        topics = [t.lower() for t in details.get("topics", [])]
        description = (details.get("description", "") or "").lower()
        name = details.get("name", "").lower()
        combined = f"{name} {description} {' '.join(topics)}"

        dept_keywords = {
            "development": ["develop", "code", "programming", "backend", "frontend", "api", "sdk", "library"],
            "design": ["design", "ui", "ux", "creative", "visual", "art"],
            "marketing": ["marketing", "seo", "content", "social", "advertising", "growth"],
            "research": ["research", "analysis", "data", "science", "nlp", "llm", "ai"],
            "testing": ["test", "qa", "quality", "automation", "benchmark"],
            "finance": ["finance", "payment", "billing", "accounting"],
            "operation": ["devops", "deploy", "infrastructure", "monitor", "ops"]
        }

        best_dept = "development"
        best_score = 0
        for dept, keywords in dept_keywords.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > best_score:
                best_score = score
                best_dept = dept

        return best_dept

    def get_skill_categories(self) -> List[str]:
        """获取Skill类别列表（基于GitHub topics）"""
        return [
            "mcp-server", "ai-agent", "automation", "data-analysis",
            "web-search", "file-management", "database", "communication",
            "development-tools", "design-tools", "marketing-tools",
            "finance-tools", "research-tools", "testing-tools"
        ]

    def get_import_history(self) -> List[Dict[str, Any]]:
        """获取导入历史"""
        return self.import_history

    def get_verification_history(self) -> List[Dict[str, Any]]:
        """获取验证历史"""
        return self.verification_history

    def get_status(self) -> Dict[str, Any]:
        """获取MCP集成状态"""
        rate_limit = self.github.get_rate_limit()
        core_limit = rate_limit.get("resources", {}).get("core", {})
        return {
            "github_authenticated": self.github.authenticated,
            "agent_sources_count": len(self.agent_sources),
            "skill_sources_count": len(self.skill_sources),
            "cached_agents": len(self.agent_cache),
            "cached_skills": len(self.skill_cache),
            "import_history_count": len(self.import_history),
            "rate_limit_remaining": core_limit.get("remaining", "unknown"),
            "rate_limit_reset": core_limit.get("reset", "unknown")
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    mcp = MCPIntegration()

    print("=" * 60)
    print("MCP GitHub集成测试")
    print("=" * 60)

    print("\n1. 搜索Agent...")
    agents = mcp.search_agents("AI assistant", limit=5)
    for a in agents:
        print(f"  - {a['name']} ({a['stars']} stars) - {a['description'][:60]}")

    print("\n2. 搜索Skill/MCP Server...")
    skills = mcp.search_skills("web search", limit=5)
    for s in skills:
        print(f"  - {s['name']} ({s['stars']} stars) - {s['description'][:60]}")

    if agents:
        print(f"\n3. 获取Agent详情: {agents[0]['repo_full_name']}")
        details = mcp.fetch_agent_details(agents[0]["repo_full_name"])
        if details:
            print(f"  描述: {details['description'][:100]}")
            print(f"  能力: {details['capabilities'][:3]}")

    print(f"\n4. MCP状态: {json.dumps(mcp.get_status(), indent=2, default=str)}")
    print("\n测试完成！")
