#!/usr/bin/env python3
"""
Example project using Agency-Agents system
"""

from agency_manager import AgencyManager

def main():
    """Run an example project"""
    # Initialize the manager
    manager = AgencyManager()
    
    print("=== Example Project: Website Redesign ===")
    print()
    
    # Define project tasks
    project_tasks = [
        {
            "department": "design",
            "agent": "ui_designer",
            "task": "Design a new website homepage with modern UI elements"
        },
        {
            "department": "design",
            "agent": "ux_researcher",
            "task": "Conduct user research to identify pain points in the current website"
        },
        {
            "department": "development",
            "agent": "frontend_developer",
            "task": "Implement the new homepage using React and Tailwind CSS"
        },
        {
            "department": "development",
            "agent": "backend_developer",
            "task": "Update the backend API to support new website features"
        },
        {
            "department": "marketing",
            "agent": "digital_marketer",
            "task": "Create a marketing campaign to promote the website redesign"
        },
        {
            "department": "content",
            "agent": "copywriter",
            "task": "Write compelling copy for the new website pages"
        }
    ]
    
    # Run the project
    print("Assigning tasks to agents...")
    print()
    
    project_results = manager.run_project("Website Redesign Project", project_tasks)
    
    # Display results
    print("=== Project Results ===")
    print()
    
    for agent, result in project_results.items():
        print(f"\n{agent}:")
        print("-" * 50)
        print(result)
        print()

if __name__ == "__main__":
    main()