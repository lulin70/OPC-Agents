"""Regression Guard: Smoke tests - verify app starts and basic routing works."""

import ast
import os
import pytest

APP_PY = os.path.join(os.path.dirname(__file__), "..", "frontend", "app.py")


def test_app_syntax_valid():
    """E1: app.py must be valid Python syntax."""
    with open(APP_PY) as f:
        source = f.read()
    try:
        ast.parse(source, filename="app.py")
    except SyntaxError as e:
        pytest.fail(f"SyntaxError in app.py at L{e.lineno}: {e.msg}")


def test_all_page_routes_defined():
    """E2: All 6 page routes must be present in routing logic."""
    with open(APP_PY) as f:
        source = f.read()

    required_routes = [
        "chat",
        "deliverables",
        "dashboard",
        "growth",
        "marketplace",
        "settings",
    ]

    has_new_routing = (
        "navigate" in source and "PageKey" in source and "page_key_map" in source
    )
    if has_new_routing:
        for route in required_routes:
            assert (
                f"PageKey.{route.upper()}" in source or f'"{route}"' in source
            ), f"Missing page route key: {route}"
        return

    missing = [
        r
        for r in required_routes
        if f'page == "{r}"' not in source and f"page == '{r}'" not in source
    ]
    assert len(missing) == 0, f"Missing page routes: {missing}"


def test_i18n_import_present():
    """E3: app.py must import i18n system."""
    with open(APP_PY) as f:
        source = f.read()
    assert (
        "from opc_manager.i18n import" in source or "import opc_manager.i18n" in source
    ), "app.py doesn't import i18n system - translation won't work!"


@pytest.mark.parametrize(
    "component_file",
    [
        "components/shared.py",
        "components/undo_panel.py",
        "components/result_cards.py",
        "components/smart_suggestions.py",
        "components/confirmation_dialog.py",
        "components/timeline_view.py",
        "components/input_autocomplete.py",
        "components/live_log_panel.py",
    ],
)
def test_component_syntax_valid(component_file):
    """E4: All component files must have valid syntax."""
    fpath = os.path.join(os.path.dirname(__file__), "..", "frontend", component_file)
    if not os.path.exists(fpath):
        pytest.skip(f"{component_file} not found")
    with open(fpath) as f:
        source = f.read()
    try:
        ast.parse(source, filename=component_file)
    except SyntaxError as e:
        pytest.fail(f"SyntaxError in {component_file} at L{e.lineno}: {e.msg}")
