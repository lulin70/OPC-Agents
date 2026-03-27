#!/usr/bin/env python3
"""
Agent management for OPC Manager
"""

import os
import json
from typing import Dict, List, Any

class AgentManager:
    """Agent manager for OPC-Agents system"""
    
    def __init__(self, agents_config: Dict[str, List[str]] = None):
        """Initialize the Agent Manager"""
        self.agents = agents_config or {}
        self.official_agents = self._load_official_agents()
    
    def _load_official_agents(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load official agents from extracted JSON files with caching and deduplication"""
        official_agents = {}
        official_agents_dir = "official_agents"
        cache_file = os.path.join(official_agents_dir, "agents_cache.json")
        
        # Try to load from cache first
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    print("Loading agents from cache...")
                    return json.load(f)
            except Exception as e:
                print(f"Error loading cache: {e}")
        
        if not os.path.exists(official_agents_dir):
            print(f"Official agents directory {official_agents_dir} not found")
            return official_agents
        
        print("Loading agents from JSON files...")
        agent_ids = set()  # To track unique agent IDs
        
        for filename in os.listdir(official_agents_dir):
            if filename.endswith('.json') and filename != "agents_cache.json":
                file_path = os.path.join(official_agents_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        agents = json.load(f)
                        for agent in agents:
                            agent_id = agent.get('name')
                            if agent_id and agent_id not in agent_ids:
                                agent_ids.add(agent_id)
                                department = agent.get('department', 'unknown')
                                if department not in official_agents:
                                    official_agents[department] = []
                                official_agents[department].append(agent)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        
        # Save to cache for future use
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(official_agents, f, ensure_ascii=False, indent=2)
            print("Agents cached successfully")
        except Exception as e:
            print(f"Error saving cache: {e}")
        
        return official_agents
    
    def get_agent_by_department(self, department: str) -> List[str]:
        """Get agents by department"""
        agents = self.agents.get(department, [])
        # 处理字典类型的代理配置（如executive_office和three_sages）
        if isinstance(agents, dict):
            return list(agents.values())
        return agents
    
    def get_official_agent_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get official agents by department"""
        return self.official_agents.get(department, [])
    
    def get_all_agents(self) -> List[str]:
        """Get all agents"""
        all_agents = []
        for department_agents in self.agents.values():
            all_agents.extend(department_agents)
        return all_agents
    
    def get_all_official_agents(self) -> List[Dict[str, Any]]:
        """Get all official agents"""
        all_agents = []
        for department_agents in self.official_agents.values():
            all_agents.extend(department_agents)
        return all_agents
    
    def get_departments(self) -> List[str]:
        """Get all departments"""
        departments = set(self.agents.keys())
        departments.update(self.official_agents.keys())
        return sorted(list(departments))
    
    def get_executive_office_agents(self) -> Dict[str, str]:
        """Get executive office agents"""
        return self.agents.get('executive_office', {})
    
    def get_three_sages(self) -> Dict[str, str]:
        """Get three sages agents"""
        return self.agents.get('three_sages', {})
