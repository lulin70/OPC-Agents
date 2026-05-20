"""Dashboard configuration model for template-based layout system.

Provides:
- LayoutType enum: COMPACT (2-col dense), FOCUSED (1-main+sidebar), MINIMAL (1-col stacked)
- DensityLevel enum: COMPACT, STANDARD, DETAILED
- DashboardConfig dataclass with save/load/persistence
- PanelConfig for per-panel enable/disable + ordering
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("data/dashboard_config.json")

ALL_PANEL_IDS = [
    "income_trend",
    "client_health",
    "task_completion",
    "financial_summary",
    "activity_timeline",
    "skill_usage",
]


class LayoutType(Enum):
    COMPACT = "compact"
    FOCUSED = "focused"
    MINIMAL = "minimal"


class DensityLevel(Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    DETAILED = "detailed"


@dataclass
class PanelConfig:
    enabled: bool = True
    order: int = 0

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "order": self.order}

    @classmethod
    def from_dict(cls, d: dict) -> "PanelConfig":
        return cls(
            enabled=d.get("enabled", True),
            order=d.get("order", 0),
        )


@dataclass
class DashboardConfig:
    layout: LayoutType = LayoutType.FOCUSED
    density: DensityLevel = DensityLevel.STANDARD
    panels: Dict[str, PanelConfig] = field(
        default_factory=lambda: {
            pid: PanelConfig(enabled=True, order=i)
            for i, pid in enumerate(ALL_PANEL_IDS)
        }
    )

    def save(self, path: Optional[Path] = None) -> None:
        target = path or DEFAULT_CONFIG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "layout": self.layout.value,
            "density": self.density.value,
            "panels": {pid: cfg.to_dict() for pid, cfg in self.panels.items()},
        }
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("[dashboard_config] Saved config to %s", target)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "DashboardConfig":
        target = path or DEFAULT_CONFIG_PATH
        if not target.exists():
            logger.info("[dashboard_config] No config at %s, using defaults", target)
            return cls()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            layout = LayoutType(raw.get("layout", "focused"))
            density = DensityLevel(raw.get("density", "standard"))
            panels_raw = raw.get("panels", {})
            panels: Dict[str, PanelConfig] = {}
            for pid in ALL_PANEL_IDS:
                if pid in panels_raw and isinstance(panels_raw[pid], dict):
                    panels[pid] = PanelConfig.from_dict(panels_raw[pid])
                else:
                    panels[pid] = PanelConfig(
                        enabled=True, order=ALL_PANEL_IDS.index(pid)
                    )
            return cls(layout=layout, density=density, panels=panels)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning(
                "[dashboard_config] Corrupted config at %s (%s), using defaults",
                target,
                exc,
            )
            return cls()

    def get_enabled_panels(self) -> List[str]:
        enabled = [pid for pid, cfg in self.panels.items() if cfg.enabled]
        enabled.sort(key=lambda pid: self.panels[pid].order)
        return enabled

    def set_panel_enabled(self, panel_id: str, enabled: bool) -> None:
        if panel_id in self.panels:
            self.panels[panel_id].enabled = enabled

    def to_session_state(self) -> dict:
        return {
            "layout": self.layout.value,
            "density": self.density.value,
            "enabled_panels": self.get_enabled_panels(),
        }
