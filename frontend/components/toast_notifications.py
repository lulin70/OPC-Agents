"""Toast notification components for OPC-Agents frontend.

Provides toast-style notification UI extracted from shared.py:
- show_success: Success toast with auto-dismiss
- show_error: Error toast notification
- show_info: Info toast notification
"""

import streamlit as st

__all__ = ["show_success", "show_error", "show_info"]


def show_success(message: str, icon: str = "✅", duration: int = 3):
    """Show a success toast notification that auto-dismisses."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            f"""
        <div class="opc-toast opc-toast-success">
            {icon} {message}
        </div>
        <style>
        .opc-toast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999;
            font-size: 15px;
            animation: slideIn 0.3s ease-out;
        }}
        @keyframes slideIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        @media (max-width: 768px) {{
            .opc-toast {{
                left: 50%;
                right: auto;
                transform: translateX(-50%);
                bottom: 16px;
                width: 90%;
                max-width: 360px;
                text-align: center;
                font-size: 14px;
                padding: 12px 16px;
            }}
        }}
        </style>
        """,
            unsafe_allow_html=True,
        )

    import time as _time

    _time.sleep(min(duration, 2))
    placeholder.empty()
    return True


def show_error(message: str, icon: str = "❌"):
    """Show an error toast notification."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            f"""
        <div class="opc-toast opc-toast-error">
            {icon} {message}
        </div>
        <style>
        .opc-toast-error {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999;
            font-size: 15px;
        }}
        @media (max-width: 768px) {{
            .opc-toast-error {{
                left: 50%;
                right: auto;
                transform: translateX(-50%);
                bottom: 16px;
                width: 90%;
                max-width: 360px;
                text-align: center;
                font-size: 14px;
                padding: 12px 16px;
            }}
        }}
        </style>
        """,
            unsafe_allow_html=True,
        )
    import time as _time

    _time.sleep(2)
    placeholder.empty()


def show_info(message: str, icon: str = "ℹ️"):
    """Show an info toast notification."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            f"""
        <div class="opc-toast opc-toast-info">
            {icon} {message}
        </div>
        <style>
        .opc-toast-info {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 999;
            font-size: 15px;
        }}
        @media (max-width: 768px) {{
            .opc-toast-info {{
                left: 50%;
                right: auto;
                transform: translateX(-50%);
                bottom: 16px;
                width: 90%;
                max-width: 360px;
                text-align: center;
                font-size: 14px;
                padding: 12px 16px;
            }}
        }}
        </style>
        """,
            unsafe_allow_html=True,
        )
    import time as _time

    _time.sleep(2)
    placeholder.empty()
