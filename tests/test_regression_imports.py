"""Regression Guard: AST Import Completeness Guard

Prevents NameError bugs like `_render_quick_undo_button not defined` before
architecture refactoring. Verifies all called functions are either imported
or defined before call site.
"""

import ast
import os
import re

APP_PY = os.path.join(os.path.dirname(__file__), "..", "frontend", "app.py")


def _get_app_source():
    with open(APP_PY, "r", encoding="utf-8") as f:
        return f.read()


def _parse_app():
    return ast.parse(_get_app_source(), filename="app.py")


class TestFunctionDefinitionOrder:
    """A1: No forward-reference functions — every def must come before its first call."""

    def test_all_functions_defined_before_first_call(self):
        tree = _parse_app()

        defs = {}
        calls_with_line = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs[node.name] = node.lineno
            elif isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Name)
                    and func.id.startswith("_")
                    and not func.id.startswith("__")
                ):
                    calls_with_line.append((func.id, node.lineno))

        problems = []
        for func_name, call_line in calls_with_line:
            if func_name in defs:
                def_line = defs[func_name]
                if def_line >= call_line:
                    problems.append(
                        f"  '{func_name}()' called at L{call_line} but defined LATER at L{def_line}"
                    )

        assert (
            len(problems) == 0
        ), f"Forward-reference functions found ({len(problems)}):\n" + "\n".join(
            problems
        )

    def test_no_phantom_function_calls(self):
        """A2: Every _xxx() call must be either defined locally OR imported."""
        tree = _parse_app()

        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.names:
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name
                        imported_names.add(name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imported_names.add(name)

        local_defs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_defs.add(node.name)

        problematic_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Name)
                    and func.id.startswith("_")
                    and not func.id.startswith("__")
                ):
                    if func.id not in local_defs and func.id not in imported_names:
                        problematic_calls.append(
                            f"  '{func.id}'() at L{node.lineno} - NEITHER defined nor imported"
                        )

        assert (
            len(problematic_calls) == 0
        ), f"Phantom function calls found ({len(problematic_calls)}):\n" + "\n".join(
            problematic_calls
        )


class TestCriticalDependencies:
    """A3: Critical functions used in deliverables must be available."""

    def test_read_file_is_available(self):
        source = _get_app_source()
        has_in_app = (
            "read_file" in source
            or "def read_file" in source
            or "from.*import.*read_file" in source
        )
        if not has_in_app:
            renderer_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "frontend",
                "renderers",
                "deliverables_renderer.py",
            )
            if os.path.exists(renderer_path):
                with open(renderer_path) as f:
                    renderer_src = f.read()
                has_in_renderer = (
                    "read_file" in renderer_src
                    or "def read_file" in renderer_src
                    or "from.*import.*read_file" in renderer_src
                )
                if has_in_renderer:
                    return
        assert (
            has_in_app or has_in_renderer
        ), "read_file() is used but neither defined nor imported in app.py or deliverables_renderer.py - will cause NameError"

    def test_t_function_is_imported_or_defined(self):
        """The i18n shorthand t() must be importable."""
        source = _get_app_source()
        has_t_import = bool(
            re.search(r"(from\s+\S+\s+import\s+.*\bt\b)|(import\s+\S*\bt\b)", source)
        )
        has_t_def = "def t(" in source or "def _t(" in source
        assert (
            has_t_import or has_t_def
        ), "t() / _t() is used for i18n but neither imported nor defined - will cause NameError"

    def test_streamlit_is_imported(self):
        """streamlit as st must be imported (critical dependency)."""
        source = _get_app_source()
        assert (
            "import streamlit" in source
        ), "streamlit is not imported - all st.xxx calls will fail with NameError"


class TestImportStructure:
    """A4: Verify import structure integrity — no duplicate imports, no broken module paths."""

    def test_no_duplicate_imports(self):
        """No function should be imported more than once (wastes memory, confusing)."""
        tree = _parse_app()
        seen_imports = {}
        duplicates = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    key = f"{node.module}.{name}"
                    line = node.lineno
                    if key in seen_imports:
                        duplicates.append(
                            f"  '{name}' from {node.module} at L{line} "
                            f"(first seen at L{seen_imports[key]})"
                        )
                    else:
                        seen_imports[key] = line
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    if name in seen_imports:
                        duplicates.append(
                            f"  '{name}' at L{node.lineno} "
                            f"(first seen at L{seen_imports[name]})"
                        )
                    else:
                        seen_imports[name] = node.lineno

        assert (
            len(duplicates) == 0
        ), f"Duplicate imports found ({len(duplicates)}):\n" + "\n".join(duplicates)

    def test_all_from_imports_have_valid_module_paths(self):
        """Every `from X import Y` should reference a plausible module path."""
        tree = _parse_app()
        suspicious = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if any(
                    part.startswith("_") and not part.startswith("__")
                    for part in parts[:-1]
                ):
                    suspicious.append(
                        f"  L{node.lineno}: from {node.module} import ... "
                        "(private submodule path)"
                    )

        assert len(suspicious) == 0, f"Suspicious import paths found:\n" + "\n".join(
            suspicious
        )


class TestFunctionCallConsistency:
    """A5: Cross-check that functions defined are actually used (dead code detection)."""

    def test_no_dead_private_functions(self):
        """Private functions (_xxx) that are defined but never called may indicate dead code.
        Allow a small threshold since some may be callback-style or event handlers."""
        tree = _parse_app()

        local_defs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_defs.add(node.name)

        called_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called_names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called_names.add(func.attr)

        dead_funcs = sorted(local_defs - called_names)
        private_dead = [
            f for f in dead_funcs if f.startswith("_") and not f.startswith("__")
        ]

        assert len(private_dead) <= 5, (
            f"Too many unused private functions ({len(private_dead)} > 5):\n"
            + "\n".join(f"  {f}" for f in private_dead)
        )


class TestModuleLevelStatements:
    """A6: Module-level code should not call undefined names."""

    def test_module_level_calls_are_safe(self):
        """Code at module level (outside any function) should only use imports/builtins.
        Allow common init patterns like load_dotenv(), init_monitoring()."""
        tree = _parse_app()

        allowed_module_level = {
            "load_dotenv",
            "init_monitoring",
            "init_secure_storage",
            "init_session_state",
            "navigate",
            "print",
            "getattr",
            "setattr",
            "hasattr",
            "isinstance",
            "type",
            "len",
            "range",
            "list",
            "dict",
            "set",
            "tuple",
            "open",
            "super",
            "property",
            "classmethod",
            "staticmethod",
        }

        module_level_calls = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Name):
                    module_level_calls.append((func.id, node.lineno))

        problems = []
        for name, line in module_level_calls:
            if name not in allowed_module_level:
                problems.append(f"  L{line}: {name}()")

        assert (
            len(problems) == 0
        ), f"Module-level calls to non-builtin/non-imported functions:\n" + "\n".join(
            problems
        )
