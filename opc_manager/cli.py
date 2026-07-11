#!/usr/bin/env python3
"""OPC-Agents CLI entry point

Provides the `opc-agents` command to launch the Streamlit web application.
"""

import sys
import os
import subprocess


def main() -> None:
    """Launch OPC-Agents Streamlit application"""
    from opc_manager.version import get_version_string

    if "--version" in sys.argv:
        print(get_version_string())
        sys.exit(0)

    if "--help" in sys.argv:
        print(get_version_string())
        print()
        print("Usage: opc-agents [OPTIONS]")
        print()
        print("Options:")
        print("  --version    Show version and exit")
        print("  --help       Show this help message and exit")
        print()
        print("Starts the OPC-Agents Streamlit web application.")
        print("The app will be available at http://localhost:8501")
        print()
        print("Environment variables (set in .env file):")
        print("  OPC_WORKSPACE      Working directory (default: current directory)")
        print("  MOKA_API_KEY       MOKA AI API key (recommended)")
        print("  GLM_API_KEY        Zhipu GLM API key")
        print("  OPENAI_API_KEY     OpenAI API key")
        print("  OLLAMA_BASE_URL    Ollama local model URL")
        sys.exit(0)

    from dotenv import load_dotenv

    workspace = os.environ.get("OPC_WORKSPACE", os.getcwd())
    env_file = os.path.join(workspace, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        example_file = os.path.join(workspace, ".env.example")
        if os.path.exists(example_file):
            print("提示: 未找到 .env 文件（已找到 .env.example 模板）")
            print("  请执行: cp .env.example .env && 编辑 .env 填入你的 API Key")
        print(f"提示: 工作目录为 {workspace}，可通过 OPC_WORKSPACE 环境变量修改")
        load_dotenv()

    try:
        from opc_manager.secure_storage import init_secure_storage

        init_secure_storage()
    except ImportError:
        pass

    import frontend

    app_path = os.path.join(os.path.dirname(frontend.__file__), "app.py")

    if not os.path.exists(app_path):
        print(f"Error: Application file not found: {app_path}", file=sys.stderr)
        print("Please ensure opc-agents is installed correctly.", file=sys.stderr)
        sys.exit(1)

    try:
        extra_args = [a for a in sys.argv[1:] if a not in ("--version", "--help")]
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", app_path] + extra_args,
            check=True,
        )
    except KeyboardInterrupt:
        print("\nOPC-Agents stopped.")
    except FileNotFoundError:
        print(
            "Error: Streamlit not found. Install with: pip install streamlit",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
