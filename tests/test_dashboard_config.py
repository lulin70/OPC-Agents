"""Tests for DashboardConfig model — layout templates, density, panel toggles, persistence."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opc_manager.dashboard_config import (
    DashboardConfig,
    LayoutType,
    DensityLevel,
    PanelConfig,
    ALL_PANEL_IDS,
)


class TestLayoutTypeEnum:
    def test_all_three_layouts_exist(self):
        assert LayoutType.COMPACT.value == "compact"
        assert LayoutType.FOCUSED.value == "focused"
        assert LayoutType.MINIMAL.value == "minimal"

    def test_layout_count(self):
        assert len(LayoutType) == 3


class TestDensityLevelEnum:
    def test_all_three_densities_exist(self):
        assert DensityLevel.COMPACT.value == "compact"
        assert DensityLevel.STANDARD.value == "standard"
        assert DensityLevel.DETAILED.value == "detailed"

    def test_density_count(self):
        assert len(DensityLevel) == 3


class TestPanelConfig:
    def test_defaults(self):
        p = PanelConfig()
        assert p.enabled is True
        assert p.order == 0

    def test_custom_values(self):
        p = PanelConfig(enabled=False, order=5)
        assert p.enabled is False
        assert p.order == 5

    def test_roundtrip_dict(self):
        p = PanelConfig(enabled=False, order=3)
        d = p.to_dict()
        restored = PanelConfig.from_dict(d)
        assert restored.enabled == p.enabled
        assert restored.order == p.order

    def test_from_dict_missing_keys(self):
        p = PanelConfig.from_dict({})
        assert p.enabled is True
        assert p.order == 0


class TestDashboardConfigDefaults:
    def test_default_layout_is_focused(self):
        c = DashboardConfig()
        assert c.layout == LayoutType.FOCUSED

    def test_default_density_is_standard(self):
        c = DashboardConfig()
        assert c.density == DensityLevel.STANDARD

    def test_default_all_panels_enabled(self):
        c = DashboardConfig()
        enabled = c.get_enabled_panels()
        assert len(enabled) == 6
        for pid in ALL_PANEL_IDS:
            assert pid in enabled

    def test_default_panel_order_matches_all_panel_ids(self):
        c = DashboardConfig()
        enabled = c.get_enabled_panels()
        assert enabled == ALL_PANEL_IDS

    def test_all_six_panel_ids_defined(self):
        assert len(ALL_PANEL_IDS) == 6
        expected = {
            "income_trend",
            "client_health",
            "task_completion",
            "financial_summary",
            "activity_timeline",
            "skill_usage",
        }
        assert set(ALL_PANEL_IDS) == expected


class TestGetEnabledPanels:
    def test_filters_disabled_panels(self):
        c = DashboardConfig()
        c.panels["task_completion"].enabled = False
        enabled = c.get_enabled_panels()
        assert "task_completion" not in enabled
        assert len(enabled) == 5

    def test_returns_empty_when_all_disabled(self):
        c = DashboardConfig()
        for pid in ALL_PANEL_IDS:
            c.panels[pid].enabled = False
        assert c.get_enabled_panels() == []

    def test_respects_order(self):
        c = DashboardConfig()
        c.panels["skill_usage"].order = -1
        enabled = c.get_enabled_panels()
        assert enabled[0] == "skill_usage"


class TestSetPanelEnabled:
    def test_enable_panel(self):
        c = DashboardConfig()
        c.panels["income_trend"].enabled = False
        c.set_panel_enabled("income_trend", True)
        assert c.panels["income_trend"].enabled is True

    def test_disable_panel(self):
        c = DashboardConfig()
        c.set_panel_enabled("client_health", False)
        assert c.panels["client_health"].enabled is False

    def test_unknown_panel_noop(self):
        c = DashboardConfig()
        c.set_panel_enabled("nonexistent_panel", False)
        assert len(c.get_enabled_panels()) == 6


class TestSaveLoadRoundtrip:
    def test_save_and_load_preserves_values(self, tmp_path):
        original = DashboardConfig(
            layout=LayoutType.COMPACT,
            density=DensityLevel.DETAILED,
        )
        original.panels["financial_summary"].enabled = False
        original.panels["skill_usage"].order = 99

        save_path = tmp_path / "dash.json"
        original.save(path=save_path)

        loaded = DashboardConfig.load(path=save_path)
        assert loaded.layout == LayoutType.COMPACT
        assert loaded.density == DensityLevel.DETAILED
        assert loaded.panels["financial_summary"].enabled is False
        assert loaded.panels["skill_usage"].order == 99

    def test_save_creates_file(self, tmp_path):
        c = DashboardConfig()
        save_path = tmp_path / "dash.json"
        c.save(path=save_path)
        assert save_path.exists()

    def test_save_creates_parent_dirs(self, tmp_path):
        c = DashboardConfig()
        save_path = tmp_path / "sub" / "dir" / "dash.json"
        c.save(path=save_path)
        assert save_path.exists()

    def test_load_nonexistent_returns_defaults(self, tmp_path):
        missing = tmp_path / "no_such_file.json"
        c = DashboardConfig.load(path=missing)
        assert c.layout == LayoutType.FOCUSED
        assert c.density == DensityLevel.STANDARD

    def test_loaded_json_structure(self, tmp_path):
        c = DashboardConfig(layout=LayoutType.MINIMAL, density=DensityLevel.COMPACT)
        save_path = tmp_path / "dash.json"
        c.save(path=save_path)

        raw = json.loads(save_path.read_text(encoding="utf-8"))
        assert raw["layout"] == "minimal"
        assert raw["density"] == "compact"
        assert "panels" in raw
        assert len(raw["panels"]) == 6


class TestInvalidConfigRecovery:
    def test_corrupted_json_returns_defaults(self, tmp_path):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("{this is not valid json!!!", encoding="utf-8")
        c = DashboardConfig.load(path=bad_path)
        assert c.layout == LayoutType.FOCUSED
        assert c.density == DensityLevel.STANDARD

    def test_empty_file_returns_defaults(self, tmp_path):
        empty_path = tmp_path / "empty.json"
        empty_path.write_text("", encoding="utf-8")
        c = DashboardConfig.load(path=empty_path)
        assert c.layout == LayoutType.FOCUSED

    def test_invalid_layout_value_fallback(self, tmp_path):
        bad_path = tmp_path / "bad_layout.json"
        bad_path.write_text(
            json.dumps(
                {"layout": "invalid_layout", "density": "standard", "panels": {}}
            ),
            encoding="utf-8",
        )
        c = DashboardConfig.load(path=bad_path)
        assert c.layout == LayoutType.FOCUSED
        assert c.density == DensityLevel.STANDARD

    def test_missing_panels_field_populates_defaults(self, tmp_path):
        partial_path = tmp_path / "partial.json"
        partial_path.write_text(
            json.dumps({"layout": "minimal", "density": "compact"}), encoding="utf-8"
        )
        c = DashboardConfig.load(path=partial_path)
        assert c.layout == LayoutType.MINIMAL
        assert c.density == DensityLevel.COMPACT
        assert len(c.get_enabled_panels()) == 6


class TestToSessionState:
    def test_session_state_dict_shape(self):
        c = DashboardConfig()
        d = c.to_session_state()
        assert "layout" in d
        assert "density" in d
        assert "enabled_panels" in d
        assert d["layout"] == "focused"
        assert d["density"] == "standard"
        assert len(d["enabled_panels"]) == 6

    def test_session_state_reflects_changes(self):
        c = DashboardConfig(layout=LayoutType.MINIMAL, density=DensityLevel.COMPACT)
        c.panels["income_trend"].enabled = False
        d = c.to_session_state()
        assert d["layout"] == "minimal"
        assert d["density"] == "compact"
        assert "income_trend" not in d["enabled_panels"]
