#!/usr/bin/env python3
import argparse
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_hr.agent_optimizer import AgentOptimizer
from opc_hr.skill_manager import SkillManager
from opc_hr.mcp_integration import MCPIntegration
from opc_hr.installation_manager import InstallationManager
from model_integration.model_manager import ModelManager

class CommandLineInterface:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='OPC-Agents Command Line Interface')
        self.subparsers = self.parser.add_subparsers(dest='command', help='Available commands')
        self.setup_commands()
        
        # 初始化各模块
        self.agent_optimizer = AgentOptimizer()
        self.skill_manager = SkillManager()
        self.mcp_integration = MCPIntegration()
        self.installation_manager = InstallationManager()
        self.model_manager = ModelManager()
    
    def setup_commands(self):
        # 代理管理命令
        agent_parser = self.subparsers.add_parser('agent', help='Manage agents')
        agent_subparsers = agent_parser.add_subparsers(dest='agent_command')
        
        # 列出所有代理
        agent_subparsers.add_parser('list', help='List all agents')
        
        # 分析代理性能
        analyze_parser = agent_subparsers.add_parser('analyze', help='Analyze agent performance')
        analyze_parser.add_argument('agent_id', help='Agent ID to analyze')
        
        # 优化代理
        optimize_parser = agent_subparsers.add_parser('optimize', help='Optimize agent')
        optimize_parser.add_argument('agent_id', help='Agent ID to optimize')
        
        # 优化所有代理
        agent_subparsers.add_parser('optimize-all', help='Optimize all agents')
        
        # 技能管理命令
        skill_parser = self.subparsers.add_parser('skill', help='Manage skills')
        skill_subparsers = skill_parser.add_subparsers(dest='skill_command')
        
        # 列出所有技能
        skill_subparsers.add_parser('list', help='List all skills')
        
        # 注册技能
        register_parser = skill_subparsers.add_parser('register', help='Register a new skill')
        register_parser.add_argument('skill_name', help='Skill name')
        register_parser.add_argument('skill_path', help='Skill path')
        
        # 推荐技能
        skill_subparsers.add_parser('recommend', help='Generate skill recommendations')
        
        # MCP集成命令
        mcp_parser = self.subparsers.add_parser('mcp', help='MCP integration commands')
        mcp_subparsers = mcp_parser.add_subparsers(dest='mcp_command')
        
        # 获取技能
        mcp_subparsers.add_parser('fetch-skills', help='Fetch skills from MCP')
        
        # 更新技能
        update_parser = mcp_subparsers.add_parser('update', help='Update a skill')
        update_parser.add_argument('skill_name', help='Skill name to update')
        
        # 安装管理命令
        install_parser = self.subparsers.add_parser('install', help='Installation commands')
        install_subparsers = install_parser.add_subparsers(dest='install_command')
        
        # 安装依赖
        install_subparsers.add_parser('dependencies', help='Install dependencies')
        
        # 检查依赖
        install_subparsers.add_parser('check', help='Check dependencies')
        
        # 优化安装
        install_subparsers.add_parser('optimize', help='Optimize installation')
        
        # 模型管理命令
        model_parser = self.subparsers.add_parser('model', help='Model management commands')
        model_subparsers = model_parser.add_subparsers(dest='model_command')
        
        # 列出所有模型
        model_subparsers.add_parser('list', help='List all models')
        
        # 设置当前模型
        set_parser = model_subparsers.add_parser('set', help='Set current model')
        set_parser.add_argument('model_name', help='Model name')
        
        # 测试模型
        test_parser = model_subparsers.add_parser('test', help='Test model')
        test_parser.add_argument('model_name', help='Model name')
        test_parser.add_argument('prompt', help='Test prompt')
        
        # 系统命令
        system_parser = self.subparsers.add_parser('system', help='System commands')
        system_subparsers = system_parser.add_subparsers(dest='system_command')
        
        # 系统状态
        system_subparsers.add_parser('status', help='Check system status')
        
        # 系统信息
        system_subparsers.add_parser('info', help='Show system information')
    
    def run(self):
        args = self.parser.parse_args()
        
        if not args.command:
            self.parser.print_help()
            return
        
        try:
            if args.command == 'agent':
                self.handle_agent_command(args)
            elif args.command == 'skill':
                self.handle_skill_command(args)
            elif args.command == 'mcp':
                self.handle_mcp_command(args)
            elif args.command == 'install':
                self.handle_install_command(args)
            elif args.command == 'model':
                self.handle_model_command(args)
            elif args.command == 'system':
                self.handle_system_command(args)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    def handle_agent_command(self, args):
        if args.agent_command == 'list':
            print("Listing all agents...")
            # 这里应该调用实际的代理列表获取方法
            print("[Agent 1] - Developer")
            print("[Agent 2] - Designer")
            print("[Agent 3] - Manager")
        elif args.agent_command == 'analyze':
            print(f"Analyzing agent {args.agent_id}...")
            result = self.agent_optimizer.analyze_performance(args.agent_id)
            print(f"Analysis result: {result}")
        elif args.agent_command == 'optimize':
            print(f"Optimizing agent {args.agent_id}...")
            result = self.agent_optimizer.optimize_agent(args.agent_id)
            print(f"Optimization result: {result}")
        elif args.agent_command == 'optimize-all':
            print("Optimizing all agents...")
            result = self.agent_optimizer.optimize_all_agents()
            print(f"Optimization result: {result}")
    
    def handle_skill_command(self, args):
        if args.skill_command == 'list':
            print("Listing all skills...")
            # 这里应该调用实际的技能列表获取方法
            print("[Skill 1] - Web Development")
            print("[Skill 2] - Graphic Design")
            print("[Skill 3] - Project Management")
        elif args.skill_command == 'register':
            print(f"Registering skill {args.skill_name} from {args.skill_path}...")
            result = self.skill_manager.register_skill(args.skill_name, args.skill_path)
            print(f"Registration result: {result}")
        elif args.skill_command == 'recommend':
            print("Generating skill recommendations...")
            result = self.skill_manager.generate_skill_recommendations()
            print(f"Recommendations: {result}")
    
    def handle_mcp_command(self, args):
        if args.mcp_command == 'fetch-skills':
            print("Fetching skills from MCP...")
            result = self.mcp_integration.fetch_skills()
            print(f"Fetched skills: {result}")
        elif args.mcp_command == 'update':
            print(f"Updating skill {args.skill_name}...")
            result = self.mcp_integration.update_skill(args.skill_name)
            print(f"Update result: {result}")
    
    def handle_install_command(self, args):
        if args.install_command == 'dependencies':
            print("Installing dependencies...")
            result = self.installation_manager.install_dependencies()
            print(f"Installation result: {result}")
        elif args.install_command == 'check':
            print("Checking dependencies...")
            result = self.installation_manager.check_dependencies()
            print(f"Check result: {result}")
        elif args.install_command == 'optimize':
            print("Optimizing installation...")
            result = self.installation_manager.optimize_installation()
            print(f"Optimization result: {result}")
    
    def handle_model_command(self, args):
        if args.model_command == 'list':
            print("Listing all models...")
            models = self.model_manager.list_models()
            for model in models:
                print(f"[Model] - {model}")
        elif args.model_command == 'set':
            print(f"Setting current model to {args.model_name}...")
            result = self.model_manager.set_current_model(args.model_name)
            print(f"Set result: {result}")
        elif args.model_command == 'test':
            print(f"Testing model {args.model_name} with prompt: {args.prompt}")
            result = self.model_manager.generate(args.prompt, model_name=args.model_name)
            print(f"Test result: {result}")
    
    def handle_system_command(self, args):
        if args.system_command == 'status':
            print("Checking system status...")
            print("System is running normally")
        elif args.system_command == 'info':
            print("System information:")
            print("OPC-Agents Version: 1.0.0")
            print("Python Version:", sys.version)
            print("OS:", os.name)

if __name__ == '__main__':
    cli = CommandLineInterface()
    cli.run()