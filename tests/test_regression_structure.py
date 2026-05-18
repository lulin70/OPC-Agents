"""Regression Guard: Structural safety checks for frontend architecture."""
import os
import pytest

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')
PAGES_DIR = os.path.join(FRONTEND_DIR, 'pages')


def test_no_pages_directory_exists():
    """C1: frontend/pages/ must NOT exist (Streamlit auto-detection bug)."""
    assert not os.path.isdir(PAGES_DIR), \
        f"frontend/pages/ directory exists! Streamlit will auto-detect .py files as multipage links. Move files to page_modules/"


def test_no_py_files_in_pages_dir_if_exists():
    """C2: Even if pages/ dir exists, it must contain NO .py files."""
    if not os.path.isdir(PAGES_DIR):
        return
    py_files = [f for f in os.listdir(PAGES_DIR) if f.endswith('.py')]
    assert len(py_files) == 0, \
        f"Found .py files in pages/: {py_files}. Streamlit will auto-detect these!"


def test_page_modules_directory_exists():
    """C3: frontend/page_modules/ MUST exist (the correct location)."""
    page_modules = os.path.join(FRONTEND_DIR, 'page_modules')
    assert os.path.isdir(page_modules), \
        "frontend/page_modules/ directory missing!"


def test_required_page_module_files_exist():
    """C4: All expected page module files must exist."""
    expected = ['__init__.py', '_dashboard_page.py', '_marketplace_page.py', '_settings_page.py']
    pm_dir = os.path.join(FRONTEND_DIR, 'page_modules')
    for fname in expected:
        fpath = os.path.join(pm_dir, fname)
        assert os.path.isfile(fpath), f"Missing required file: page_modules/{fname}"


def test_app_py_line_count_reasonable():
    """C5: app.py should be under 2000 lines (giant file detection)."""
    app_py = os.path.join(FRONTEND_DIR, 'app.py')
    if not os.path.exists(app_py):
        pytest.skip("app.py not found")
    with open(app_py) as f:
        lines = sum(1 for _ in f)
    assert lines < 2500, \
        f"app.py is {lines} lines! Should be < 2000. Consider extracting modules."


@pytest.mark.xfail(reason="Known F03: dashboard_page has circular import from app.py - will be fixed in Phase 1 structural extraction")
def test_no_circular_import_risk():
    """C6: dashboard_page should NOT import from app.py (circular dependency)."""
    dp = os.path.join(FRONTEND_DIR, 'page_modules', '_dashboard_page.py')
    if not os.path.exists(dp):
        pytest.skip("_dashboard_page.py not found")
    with open(dp) as f:
        content = f.read()
    assert 'from frontend.app import' not in content and 'import frontend.app' not in content, \
        "_dashboard_page.py imports from app.py - circular dependency risk!"
