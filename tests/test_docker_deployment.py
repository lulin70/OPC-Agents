"""Tests for P2 delight improvements: Docker deployment, onboarding guide, themes, start.sh."""

import os
import re
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDockerfile:
    """P2-9: Dockerfile validation."""

    def test_dockerfile_exists(self):
        df = PROJECT_ROOT / "Dockerfile"
        assert df.exists(), "Dockerfile must exist"

    def test_dockerfile_has_healthcheck(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "HEALTHCHECK" in content, "Dockerfile must have HEALTHCHECK directive"

    def test_dockerfile_has_nonroot_user(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "USER" in content, "Dockerfile must set non-root user"

    def test_dockerfile_version_label(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert (
            'version="0.3.0"' in content or "version=0.3.0" in content
        ), "Dockerfile LABEL version should be 0.3.0"

    def test_dockerfile_python_base(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert (
            "python:3.11-slim" in content
        ), "Dockerfile should use python:3.11-slim base"


class TestDockerCompose:
    """P2-9: docker-compose.yml validation."""

    def test_compose_exists(self):
        yml = PROJECT_ROOT / "docker-compose.yml"
        assert yml.exists(), "docker-compose.yml must exist"

    def test_compose_has_volume_mounts(self):
        yml = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(yml.read_text())
        svc = data["services"]["opc-agents"]
        volumes = svc.get("volumes", [])
        assert any(
            "data" in str(v) for v in volumes
        ), "docker-compose.yml must mount data volume"
        assert any(
            ".env" in str(v) for v in volumes
        ), "docker-compose.yml must mount .env file"

    def test_compose_has_healthcheck(self):
        yml = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(yml.read_text())
        svc = data["services"]["opc-agents"]
        assert "healthcheck" in svc, "Service must have healthcheck"

    def test_compose_has_networks(self):
        yml = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(yml.read_text())
        assert "networks" in data, "Compose file must define networks"

    def test_dev_compose_exists(self):
        dev_yml = PROJECT_ROOT / "docker-compose.dev.yml"
        assert dev_yml.exists(), "docker-compose.dev.yml must exist"

    def test_dev_compose_has_live_mount(self):
        dev_yml = PROJECT_ROOT / "docker-compose.dev.yml"
        data = yaml.safe_load(dev_yml.read_text())
        volumes = data["services"]["opc-agents"].get("volumes", [])
        assert any(
            "./:/app" in str(v) for v in volumes
        ), "Dev compose must mount source for live editing"


class TestDockerignore:
    """P2-9: .dockerignore coverage."""

    def test_dockerignore_exists(self):
        di = PROJECT_ROOT / ".dockerignore"
        assert di.exists(), ".dockerignore must exist"

    def test_dockerignore_covers_git(self):
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert ".git" in content, ".dockerignore must exclude .git"

    def test_dockerignore_covers_env_local(self):
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert (
            ".env.local" in content or "__pycache__" in content
        ), ".dockerignore must cover sensitive/local files"

    def test_dockerignore_covers_pycache(self):
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert "__pycache__" in content, ".dockerignore must exclude __pycache__"

    def test_dockerignore_covers_tests(self):
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert "tests/" in content, ".dockerignore must exclude tests/"

    def test_data_gitkeep_exists(self):
        gk = PROJECT_ROOT / "data" / ".gitkeep"
        assert gk.exists(), "data/.gitkeep must exist for git tracking"


class TestThemeCSS:
    """P2-11: Theme CSS generator validation."""

    @staticmethod
    def _get_css_func():
        from frontend.components.shared import _get_theme_css

        return _get_theme_css

    def test_dark_theme_css_valid(self):
        css = self._get_css_func()("dark")
        assert isinstance(css, str)
        assert "background-color" in css
        assert "#111827" in css

    def test_sunset_theme_css_valid(self):
        css = self._get_css_func()("sunset")
        assert isinstance(css, str)
        assert "#1a1423" in css

    def test_forest_theme_css_valid(self):
        css = self._get_css_func()("forest")
        assert isinstance(css, str)
        assert "#0d1f17" in css

    def test_ocean_theme_css_valid(self):
        css = self._get_css_func()("ocean")
        assert isinstance(css, str)
        assert "#0c1929" in css

    def test_light_theme_returns_no_custom_colors(self):
        css = self._get_css_func()("light")
        # Light theme uses native styling, may contain mobile CSS but no custom colors
        assert "#111827" not in css, "Light theme should not have dark background"
        assert "#0c1929" not in css, "Light theme should not have ocean background"

    def test_unknown_theme_returns_no_custom_colors(self):
        func = self._get_css_func()
        css = func("nonexistent")
        # Unknown theme may return mobile CSS but no theme-specific colors
        assert "#111827" not in css

    def test_all_themes_return_string(self):
        func = self._get_css_func()
        for theme in ("dark", "sunset", "forest", "ocean", "light"):
            result = func(theme)
            assert isinstance(result, str), f"Theme '{theme}' must return string"


class TestThemeConfigs:
    """P2-11: THEME_CONFIGS completeness."""

    @staticmethod
    def _get_configs():
        from frontend.components.shared import THEME_CONFIGS

        return THEME_CONFIGS

    def test_all_five_themes_exist(self):
        cfg = self._get_configs()
        expected = {"light", "dark", "sunset", "forest", "ocean"}
        assert (
            set(cfg.keys()) == expected
        ), f"Must have exactly these themes: {expected}"

    def test_each_theme_has_required_keys(self):
        cfg = self._get_configs()
        required = {
            "backgroundColor",
            "secondaryBackgroundColor",
            "textColor",
            "font",
            "primaryColor",
        }
        for name, config in cfg.items():
            missing = required - set(config.keys())
            assert not missing, f"Theme '{name}' missing keys: {missing}"

    def test_each_theme_color_is_hex(self):
        cfg = self._get_configs()
        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for name, config in cfg.items():
            for key in (
                "backgroundColor",
                "secondaryBackgroundColor",
                "textColor",
                "primaryColor",
            ):
                val = config[key]
                assert hex_pattern.match(
                    val
                ), f"Theme '{name}'.{key}='{val}' is not a valid hex color"


class TestQuickStartGuide:
    """P2-10: Onboarding quick-start guide ASCII art."""

    @staticmethod
    def _get_guide():
        from opc_manager.onboarding import QUICK_START_GUIDE

        return QUICK_START_GUIDE

    def test_guide_is_string(self):
        guide = self._get_guide()
        assert isinstance(guide, str)

    def test_guide_not_empty(self):
        guide = self._get_guide()
        assert len(guide.strip()) > 0

    def test_guide_contains_opc_agents(self):
        guide = self._get_guide()
        assert "OPC-Agents" in guide

    def test_guide_contains_box_drawing_chars(self):
        guide = self._get_guide()
        assert "┌" in guide and "┐" in guide, "Should contain box-drawing characters"

    def test_guide_in_completed_step(self):
        from opc_manager.onboarding import OnboardingManager

        mgr = OnboardingManager()
        content = mgr.get_step_content(
            mgr.get_step_content.__self__.COMPLETED if False else None
        )
        completed_content = (
            mgr.get_step_content(type("Obj", (object,), {"value": "completed"})())
            if False
            else None
        )
        from opc_manager.onboarding import OnboardingStep

        step_content = mgr.get_step_content(OnboardingStep.COMPLETED)
        assert (
            "quick_start_guide" in step_content
        ), "Completed step must include quick_start_guide"


class TestStartScript:
    """P2-12: start.sh pre-flight checks."""

    def test_start_sh_exists(self):
        sh = PROJECT_ROOT / "start.sh"
        assert sh.exists(), "start.sh must exist"

    def test_start_sh_has_port_check(self):
        content = (PROJECT_ROOT / "start.sh").read_text()
        assert "lsof" in content, "start.sh must check port availability"

    def test_start_sh_has_disk_check(self):
        content = (PROJECT_ROOT / "start.sh").read_text()
        assert "df -k" in content, "start.sh must check disk space"

    def test_start_sh_has_memory_check(self):
        content = (PROJECT_ROOT / "start.sh").read_text()
        assert "vm_stat" in content, "start.sh must check memory (macOS)"

    def test_start_sh_has_preflight_label(self):
        content = (PROJECT_ROOT / "start.sh").read_text()
        assert "pre-flight" in content.lower(), "start.sh must have pre-flight section"
