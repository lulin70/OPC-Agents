#!/usr/bin/env python3
"""OPC-Agents CLI entry point

Provides the `opc-agents` command to launch the Streamlit web application.
"""

import sys
import os
import subprocess


def main():
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
        print("  MOKA_API_KEY       MOKA AI API key (recommended)")
        print("  GLM_API_KEY        Zhipu GLM API key")
        print("  OPENAI_API_KEY     OpenAI API key")
        print("  OLLAMA_BASE_URL    Ollama local model URL")
        sys.exit(0)

    from dotenv import load_dotenv
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
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", app_path],
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
