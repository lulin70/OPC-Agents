"""
能力发现器集成演示
演示总裁办如何主动检测能力缺口并通过人事部获取新能力
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_hr.capability_discovery import CapabilityDiscovery
from opc_skills import SkillRegistry, ClawHubIntegration
from opc_hr.hr_enhancement import HREnhancement


def demo_capability_discovery_workflow():
    """演示能力发现完整工作流"""
    
    print("=" * 80)
    print("能力发现器集成演示")
    print("=" * 80)
    print()
    
    # 初始化组件
    print("1️⃣ 初始化组件...")
    skill_registry = SkillRegistry()
    clawhub = ClawHubIntegration()
    capability_discovery = CapabilityDiscovery(
        skill_registry=skill_registry,
        clawhub=clawhub
    )
    print(f"   ✅ 能力发现器初始化完成")
    print()
    
    # 模拟用户需求场景
    scenarios = [
        {
            'user_request': "我需要分析这份 PDF 文档并提取关键信息",
            'task_type': "文档处理"
        },
        {
            'user_request': "帮我制作一个 Excel 图表展示销售数据",
            'task_type': "数据分析"
        },
        {
            'user_request': "搜索最新的 AI 资讯并生成摘要报告",
            'task_type': "信息收集"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"{'='*80}")
        print(f"场景 {i}: {scenario['task_type']}")
        print(f"{'='*80}")
        print(f"用户需求：{scenario['user_request']}")
        print()
        
        # 步骤 1: 分析用户需求
        print("2️⃣ 分析用户需求...")
        keywords = capability_discovery.analyze_user_request(scenario['user_request'])
        print(f"   提取关键词：{keywords[:5]}...")  # 只显示前 5 个
        print()
        
        # 步骤 2: 检测能力缺口
        print("3️⃣ 检测能力缺口...")
        gaps = capability_discovery.detect_capability_gap(
            required_keywords=keywords,
            context=scenario['task_type']
        )
        
        if gaps:
            print(f"   ⚠️ 检测到 {len(gaps)} 个能力缺口:")
            for gap in gaps[:3]:  # 只显示前 3 个
                print(f"      - {gap.skill_name} (优先级：{gap.priority})")
        else:
            print(f"   ✅ 系统已具备所需能力")
        print()
        
        # 步骤 3: 搜索替代技能
        if gaps:
            print("4️⃣ 搜索替代技能...")
            all_candidates = []
            for gap in gaps[:2]:  # 只处理前 2 个缺口
                candidates = capability_discovery.search_alternatives(gap)
                if candidates:
                    print(f"   为 '{gap.skill_name}' 找到 {len(candidates)} 个候选")
                    all_candidates.extend(candidates)
            
            if not all_candidates:
                print(f"   ⚠️ ClawHub 未返回结果（演示环境限制）")
                print(f"   💡 实际环境中会从 ClawHub/MCP 搜索技能")
            print()
            
            # 步骤 4: 评估候选技能
            if all_candidates:
                print("5️⃣ 评估候选技能...")
                best_candidate = capability_discovery.evaluate_and_test(
                    all_candidates[:5],  # 只评估前 5 个
                    gaps[0]
                )
                
                if best_candidate:
                    print(f"   ✅ 选择最佳候选：{best_candidate.get('name', 'Unknown')}")
                    print(f"      分类：{best_candidate.get('category', 'Unknown')}")
                    print(f"      评分：{best_candidate.get('rating', 0)}")
                    print(f"      下载量：{best_candidate.get('download_count', 0)}")
                else:
                    print(f"   ⚠️ 没有合适的候选技能")
                print()
                
                # 步骤 5: 生成推荐
                if best_candidate:
                    print("6️⃣ 生成推荐...")
                    user = {'name': '演示用户'}
                    result = capability_discovery.recommend_to_user(
                        best_candidate,
                        gaps[0],
                        user
                    )
                    
                    if result['success']:
                        rec = result['recommendation']
                        print(f"   ✅ 推荐成功！")
                        print(f"      推荐技能：{rec['skill']['name']}")
                        print(f"      推荐理由：{rec['reason'][:80]}...")
                        print(f"      安装好处:")
                        for benefit in rec['benefits'][:3]:
                            print(f"         - {benefit}")
                    else:
                        print(f"   ⚠️ 推荐失败：{result['reason']}")
                    print()
        
        # 步骤 6: 总结
        print("7️⃣ 总结...")
        print(f"   💡 当前系统有 {len(skill_registry.list_skills())} 个技能")
        print(f"   💡 能力缺口：{len(gaps) if gaps else 0} 个")
        print(f"   💡 建议：安装新技能或招聘新 Agent")
        print()
        
        print()
    
    # 总结
    print("=" * 80)
    print("演示总结")
    print("=" * 80)
    print()
    print("✅ 能力发现器可以:")
    print("   1. 分析用户需求，提取所需技能关键词")
    print("   2. 检测系统能力缺口")
    print("   3. 从 ClawHub/MCP 搜索替代技能")
    print("   4. 评估候选技能（名称/分类/评分/下载量/安全性）")
    print("   5. 向用户生成推荐（含好处和风险分析）")
    print()
    print("⚠️ 当前限制:")
    print("   - 能力发现器还未集成到总裁办核心流程")
    print("   - ClawHub 搜索在演示环境中返回空结果")
    print("   - 需要实际部署 ClawHub/MCP 服务器")
    print()
    print("📋 下一步行动:")
    print("   1. 将能力发现器集成到 OPCManager 的任务分解流程")
    print("   2. 在任务分配前检测能力缺口")
    print("   3. 提供用户界面让用户确认安装新技能/Agent")
    print("   4. 安装完成后重新匹配 Agent 并执行任务")
    print()


if __name__ == '__main__':
    demo_capability_discovery_workflow()
