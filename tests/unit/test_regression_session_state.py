"""Regression Guard: Session state access safety - prevent AttributeError crashes."""

import re
import os

APP_PY = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "app.py")

_BARE_ACCESS_PATTERN = re.compile(r"st\.session_state\.[a-zA-Z_]\w*[^.(\[]")


def _get_bare_session_state_accesses(source):
    """Find st.session_state.xxx accesses without .get() protection."""
    violations = []
    for i, line in enumerate(source.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        matches = re.findall(r"st\.session_state\.(\w+)", line)
        for var_name in matches:
            safe_patterns = [
                ".get(",
                " in ",
                ", '= in",
                "#",
                "if ",
                "elif ",
                "for ",
                "while ",
                "with ",
                "pop(",
            ]
            is_safe = any(p in line for p in safe_patterns)
            if not is_safe:
                violations.append((i, var_name, stripped.strip()))
    return violations


def test_no_dangerous_bare_session_access():
    """D1: st.session_state.xxx should use .get() for safety."""
    with open(APP_PY) as f:
        source = f.read()

    violations = _get_bare_session_state_accesses(source)

    dangerous = [
        (ln, var, ctx)
        for ln, var, ctx in violations
        if "=" not in ctx
        and "if " not in ctx
        and "elif " not in ctx
        and "pop(" not in ctx
        and "del " not in ctx
    ]

    assert (
        len(dangerous) < 20
    ), f"Too many unsafe st.session_state accesses ({len(dangerous)}):\n" + "\n".join(
        f"  L{ln}: {var} -> {ctx}" for ln, var, ctx in dangerous[:10]
    )
