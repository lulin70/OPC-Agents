"""Dark theme E2E tests for OPC-Agents UI (UI_DESIGN_v0.5.1.md §3).

Validates the Morandi dark theme tokens are applied to the DOM and that color
contrast meets WCAG AA / AAA:

1. ``test_morandi_dark_theme_applied`` — selecting morandi_dark sets the
   background to ``#1F1B16`` (warm deep brown, UI_DESIGN §3.1).
2. ``test_theme_switching_no_visual_jump`` — switching between morandi_light
   and morandi_dark keeps the primary color at ``#6B7B8C`` (UI_DESIGN §3.2).
3. ``test_dark_theme_text_contrast`` — text color ``#E8E0D5`` against
   background ``#1F1B16`` must have contrast >= 7:1 (AAA).

Run:
    pytest tests/e2e/test_theme_dark.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


# ============================================================
# Constants — Morandi color tokens (UI_DESIGN_v0.5.1.md §3.1)
# ============================================================

MORANDI_DARK_BG = "#1F1B16"
MORANDI_LIGHT_BG = "#F5F2EE"
MORANDI_PRIMARY = "#6B7B8C"
MORANDI_DARK_TEXT = "#E8E0D5"


# ============================================================
# Helpers
# ============================================================


def _wait_for_streamlit_content(page, timeout: int = 15000) -> None:
    """Wait for Streamlit to fully render its main content area."""
    try:
        page.wait_for_selector("[data-testid='stMainBlockContainer']", timeout=timeout)
        page.wait_for_function(
            """() => {
                const main = document.querySelector("[data-testid='stMainBlockContainer']");
                if (!main) return false;
                const content = main.querySelectorAll(
                    "[data-testid='stMarkdown'], [data-testid='stButton'], "
                    "[data-testid='stMetric'], [data-testid='stTabs'], "
                    "[data-testid='stAlert'], [data-testid='stExpander']"
                );
                return content.length > 0;
            }""",
            timeout=timeout,
        )
    except Exception:
        page.wait_for_timeout(5000)


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse ``#RRGGBB`` to an ``(r, g, b)`` tuple."""
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _color_matches(color: str, target_hex: str, tolerance: int = 8) -> bool:
    """Return True if ``color`` (rgb/rgba/hex string) matches ``target_hex`` within ``tolerance``."""
    target = _hex_to_rgb(target_hex)

    if color.startswith("#"):
        actual = _hex_to_rgb(color)
    else:
        # "rgb(r, g, b)" or "rgba(r, g, b, a)"
        inside = color[color.find("(") + 1 : color.rfind(")")]
        parts = [p.strip() for p in inside.split(",")]
        actual = (int(float(parts[0])), int(float(parts[1])), int(float(parts[2])))

    return all(abs(actual[i] - target[i]) <= tolerance for i in range(3))


def _select_theme_via_sidebar(page, theme_value: str) -> None:
    """Select a theme in the sidebar primary theme selector.

    The primary selector offers ``morandi_light`` and ``morandi_dark``. The
    selectbox renders as the first ``[data-testid='stSelectbox']`` in the
    sidebar; its visible label depends on i18n. We open the dropdown and
    click the option whose data-value matches ``theme_value``.
    """
    # First selectbox in the sidebar is the primary theme selector
    selectboxes = page.locator("[data-testid='stSelectbox']")
    assert selectboxes.count() >= 1, "No theme selectbox found in sidebar"
    theme_sb = selectboxes.first

    # Click to open the dropdown
    theme_sb.click()
    page.wait_for_timeout(500)

    # Option text may be localized; match by visible option containing the
    # theme's identifier fragments.
    option_aliases = {
        "morandi_light": ["Morandi Light", "morandi_light", "浅色"],
        "morandi_dark": ["Morandi Dark", "morandi_dark", "深色"],
    }
    candidates = option_aliases.get(theme_value, [theme_value])
    clicked = False
    for alias in candidates:
        opt = page.locator("[role='option']").filter(has_text=alias).first
        try:
            opt.wait_for(state="visible", timeout=1500)
            opt.click()
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        # Fallback: click the option at index 0 (morandi_light) or 1 (morandi_dark)
        options = page.locator("[role='option']")
        idx = 0 if theme_value == "morandi_light" else 1
        try:
            options.nth(idx).click()
            clicked = True
        except Exception as exc:
            raise RuntimeError(
                "Could not select theme '{}': {}".format(theme_value, exc)
            )
    page.wait_for_timeout(2500)


def _get_main_background_color(page) -> str:
    """Return the computed background color of the .stApp element."""
    return page.evaluate("""() => {
            const el = document.querySelector('.stApp') || document.body;
            return window.getComputedStyle(el).backgroundColor;
        }""")


def _get_primary_color(page) -> str:
    """Return the primary color used by the first visible primary button.

    Falls back to the Streamlit ``--primary-color`` CSS var if no primary
    button is rendered on the page.
    """
    return page.evaluate("""() => {
            // Prefer Streamlit primary buttons (type="primary")
            const primaryBtn = document.querySelector(
                '.stButton button[kind="primary"], ' +
                'button[data-testid="stBaseButton-primary"]'
            );
            if (primaryBtn) {
                return window.getComputedStyle(primaryBtn).backgroundColor;
            }
            // Fallback: read Streamlit CSS variable
            const cssVar = getComputedStyle(document.documentElement)
                .getPropertyValue('--primary-color').trim();
            if (cssVar) return cssVar;
            // Last resort: any button's background
            const anyBtn = document.querySelector('.stButton button');
            if (anyBtn) return window.getComputedStyle(anyBtn).backgroundColor;
            return '';
        }""")


def _get_text_color(page) -> str:
    """Return the computed text color of the first visible markdown paragraph."""
    return page.evaluate("""() => {
            const md = document.querySelector('.stMarkdown, [data-testid="stMarkdown"]');
            if (md) return window.getComputedStyle(md).color;
            return window.getComputedStyle(document.body).color;
        }""")


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Compute the WCAG contrast ratio between two ``#RRGGBB`` colors."""

    def _relative_luminance(rgb: tuple[int, int, int]) -> float:
        def _linearize(c: float) -> float:
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = rgb
        return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)

    fg = _hex_to_rgb(fg_hex)
    bg = _hex_to_rgb(bg_hex)
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ============================================================
# TC-TH-01: morandi_dark background applied
# ============================================================


class TestMorandiDarkTheme:
    """Verify morandi_dark theme tokens are applied to the DOM."""

    def test_morandi_dark_theme_applied(self, page):
        """TC-TH-01: After selecting morandi_dark, background is #1F1B16.

        Scenario: User selects morandi_dark in the sidebar
        Expected: .stApp background-color matches #1F1B16 (warm deep brown)
        """
        _wait_for_streamlit_content(page)

        _select_theme_via_sidebar(page, "morandi_dark")

        bg = _get_main_background_color(page)
        assert _color_matches(
            bg, MORANDI_DARK_BG, tolerance=10
        ), "morandi_dark background should be {} but got {}".format(MORANDI_DARK_BG, bg)


# ============================================================
# TC-TH-02: Theme switching keeps primary color stable
# ============================================================


class TestThemeSwitchingNoJump:
    """Verify primary color stays #6B7B8C across light/dark switching."""

    def test_theme_switching_no_visual_jump(self, page):
        """TC-TH-02: morandi_light <-> morandi_dark keeps primary #6B7B8C.

        Scenario: User toggles between morandi_light and morandi_dark
        Expected: primary color stays at #6B7B8C in both themes (brand consistency)
        """
        _wait_for_streamlit_content(page)

        # 1) Start on morandi_light, capture primary color
        _select_theme_via_sidebar(page, "morandi_light")
        primary_light = _get_primary_color(page)

        # 2) Switch to morandi_dark, capture primary color
        _select_theme_via_sidebar(page, "morandi_dark")
        primary_dark = _get_primary_color(page)

        # 3) Both should match MORANDI_PRIMARY (#6B7B8C) per UI_DESIGN §3.2.
        # Streamlit may render the primary button as a slightly different
        # shade when hovered/active; allow a generous tolerance.
        assert _color_matches(
            primary_light, MORANDI_PRIMARY, tolerance=30
        ), "morandi_light primary color should be {} but got {}".format(
            MORANDI_PRIMARY, primary_light
        )
        assert _color_matches(
            primary_dark, MORANDI_PRIMARY, tolerance=30
        ), "morandi_dark primary color should be {} but got {}".format(
            MORANDI_PRIMARY, primary_dark
        )


# ============================================================
# TC-TH-03: Dark theme text contrast >= 7:1 (AAA)
# ============================================================


class TestDarkThemeTextContrast:
    """Verify text vs background contrast in morandi_dark meets AAA."""

    def test_dark_theme_text_contrast(self, page):
        """TC-TH-03: morandi_dark text #E8E0D5 vs background #1F1B16 >= 7:1.

        Scenario: User in morandi_dark reads text content
        Expected: text/background contrast >= 7:1 (WCAG AAA)

        We compute the theoretical ratio (per UI_DESIGN §3.1 table: 11.2:1)
        AND verify the rendered colors match the design tokens.
        """
        # 1) Theoretical check (deterministic, no Playwright needed)
        theoretical_ratio = _contrast_ratio(MORANDI_DARK_TEXT, MORANDI_DARK_BG)
        assert (
            theoretical_ratio >= 7.0
        ), "Theoretical contrast {} should be >= 7:1 (AAA)".format(theoretical_ratio)

        # 2) Verify rendered colors match the design tokens in morandi_dark
        _wait_for_streamlit_content(page)
        _select_theme_via_sidebar(page, "morandi_dark")

        bg = _get_main_background_color(page)
        assert _color_matches(
            bg, MORANDI_DARK_BG, tolerance=10
        ), "Rendered background {} does not match {}".format(bg, MORANDI_DARK_BG)

        text_color = _get_text_color(page)
        assert _color_matches(
            text_color, MORANDI_DARK_TEXT, tolerance=30
        ), "Rendered text color {} does not match {}".format(
            text_color, MORANDI_DARK_TEXT
        )

        # 3) Compute the actual rendered ratio and assert >= 7:1
        rendered_ratio = _contrast_ratio(
            _normalize_to_hex(text_color),
            _normalize_to_hex(bg),
        )
        assert (
            rendered_ratio >= 7.0
        ), "Rendered contrast {} should be >= 7:1 (AAA); " "text={} bg={}".format(
            rendered_ratio, text_color, bg
        )


def _normalize_to_hex(color: str) -> str:
    """Convert ``rgb(r, g, b)`` / ``rgba(...)`` / ``#RRGGBB`` to ``#RRGGBB``."""
    if color.startswith("#"):
        return color
    inside = color[color.find("(") + 1 : color.rfind(")")]
    parts = [p.strip() for p in inside.split(",")]
    return "#{:02X}{:02X}{:02X}".format(
        int(float(parts[0])), int(float(parts[1])), int(float(parts[2]))
    )
