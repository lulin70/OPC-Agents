"""Toast notification components for OPC-Agents frontend.

Provides toast-style notification UI using Streamlit's built-in st.toast():
- show_success: Success toast with  icon
- show_error: Error toast with  icon
- show_info: Info toast with  icon
"""

import streamlit as st

__all__ = ["show_success", "show_error", "show_info"]


def show_success(message: str, icon: str | None = None):
    """Show a success toast notification."""
    st.toast(message, icon=icon)


def show_error(message: str, icon: str | None = None):
    """Show an error toast notification."""
    st.toast(message, icon=icon)


def show_info(message: str, icon: str | None = None):
    """Show an info toast notification."""
    st.toast(message, icon=icon)
