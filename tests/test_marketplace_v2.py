"""Tests for Skill Marketplace V2 features.

Covers:
- _filter_and_sort_skills: search, category, sort, combined filters
- Version pinning: save/load/remove installed versions
- Category extraction and ALL_CATEGORIES constant
- Install count simulation
- Detail view data preparation
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frontend.page_modules._marketplace_page import (
    ALL_CATEGORIES,
    SORT_OPTIONS,
    _filter_and_sort_skills,
    _simulate_install_count,
    _get_installed_versions_file,
    _load_installed_versions_for_write,
    _save_installed_version,
    _remove_installed_version,
)


SAMPLE_SKILLS = [
    {
        "skill_id": "crm_pro",
        "name": "CRM Pro",
        "description": "Customer relationship management tool",
        "version": "2.1.0",
        "category": "CRM",
        "author": "OPC Team",
        "tags": ["sales", "customer"],
    },
    {
        "skill_id": "finance_tracker",
        "name": "Finance Tracker",
        "description": "Track income and expenses",
        "version": "1.5.0",
        "category": "Finance",
        "author": "Finance Dev",
        "tags": ["money", "accounting"],
    },
    {
        "skill_id": "email_blaster",
        "name": "Email Blaster",
        "description": "Bulk email sending",
        "version": "3.0.0",
        "category": "Email",
        "author": "Mail Team",
        "tags": ["communication", "marketing"],
    },
    {
        "skill_id": "calendar_sync",
        "name": "Calendar Sync",
        "description": "Sync calendars across platforms",
        "version": "1.0.0",
        "category": "Calendar",
        "author": "Sync Dev",
        "tags": ["scheduling"],
    },
    {
        "skill_id": "analytics_dash",
        "name": "Analytics Dashboard",
        "description": "Business analytics dashboard",
        "version": "1.2.0",
        "category": "Dashboard",
        "author": "Data Team",
        "tags": ["analytics", "visualization"],
    },
]


class TestFilterAndSortSkills:
    """Tests for _filter_and_sort_skills function."""

    def test_no_filters_returns_all(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "", [], "name_asc")
        assert len(result) == 5

    def test_search_by_name(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "CRM", [], "name_asc")
        assert len(result) == 1
        assert result[0]["name"] == "CRM Pro"

    def test_search_by_description(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "bulk email", [], "name_asc")
        assert len(result) == 1
        assert result[0]["name"] == "Email Blaster"

    def test_search_case_insensitive(self):
        result_lower = _filter_and_sort_skills(SAMPLE_SKILLS, "crm", [], "name_asc")
        result_upper = _filter_and_sort_skills(SAMPLE_SKILLS, "CRM", [], "name_asc")
        assert result_lower == result_upper

    def test_search_no_match(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "xyznonexistent", [], "name_asc")
        assert len(result) == 0

    def test_category_filter_single(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "", ["Finance"], "name_asc")
        assert len(result) == 1
        assert result[0]["category"] == "Finance"

    def test_category_filter_multiple(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "", ["CRM", "Email"], "name_asc")
        assert len(result) == 2
        categories = {s["category"] for s in result}
        assert categories == {"CRM", "Email"}

    def test_category_filter_no_match(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "", ["Security"], "name_asc")
        assert len(result) == 0

    def test_combined_search_and_category(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "dashboard", ["Dashboard"], "name_asc")
        assert len(result) == 1
        assert result[0]["name"] == "Analytics Dashboard"

    def test_combined_search_and_category_no_overlap(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "CRM", ["Finance"], "name_asc")
        assert len(result) == 0

    def test_sort_name_asc(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "", [], "name_asc")
        names = [s["name"] for s in result]
        assert names == sorted(names)

    def test_sort_name_desc(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "", [], "name_desc")
        names = [s["name"] for s in result]
        assert names == sorted(names, reverse=True)

    def test_sort_popular_returns_all(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "", [], "popular")
        assert len(result) == 5

    def test_sort_popular_is_deterministic(self):
        result1 = _filter_and_sort_skills(SAMPLE_SKILLS, "", [], "popular")
        result2 = _filter_and_sort_skills(SAMPLE_SKILLS, "", [], "popular")
        assert result1 == result2

    def test_empty_skill_list(self):
        result = _filter_and_sort_skills([], "test", ["CRM"], "name_asc")
        assert result == []

    def test_search_with_partial_match(self):
        result = _filter_and_sort_skills(SAMPLE_SKILLS, "mail", [], "name_asc")
        assert len(result) >= 1
        assert all("mail" in s["name"].lower() or "mail" in s["description"].lower() for s in result)

    def test_skills_with_missing_fields(self):
        broken_skills = [{"skill_id": "x"}, {"name": "NoId"}]
        result = _filter_and_sort_skills(broken_skills, "", [], "name_asc")
        assert len(result) == 2


class TestSimulateInstallCount:
    """Tests for _simulate_install_count helper."""

    def test_returns_int(self):
        count = _simulate_install_count("test_skill")
        assert isinstance(count, int)

    def test_range_within_bounds(self):
        for skill_id in ["a", "abc", "skill_123", "long-skill-name-here"]:
            count = _simulate_install_count(skill_id)
            assert 0 <= count < 10000

    def test_deterministic_same_input(self):
        c1 = _simulate_install_count("same_id")
        c2 = _simulate_install_count("same_id")
        assert c1 == c2

    def test_different_ids_different_counts(self):
        counts = {_simulate_install_count(f"skill_{i}") for i in range(20)}
        assert len(counts) > 1

    def test_empty_string_id(self):
        count = _simulate_install_count("")
        assert isinstance(count, int)
        assert 0 <= count < 10000


class TestAllCategoriesConstant:
    """Tests for ALL_CATEGORIES list."""

    def test_not_empty(self):
        assert len(ALL_CATEGORIES) > 0

    def test_expected_categories_present(self):
        expected = {"CRM", "Finance", "Email", "Calendar", "Social",
                     "Knowledge", "Report", "Task", "Proposal", "Tax",
                     "Dashboard", "Competitor", "Pricing", "Invoice",
                     "Security", "Monitoring"}
        assert set(ALL_CATEGORIES) == expected

    def test_count_sixteen(self):
        assert len(ALL_CATEGORIES) == 16


class TestSortOptionsConstant:
    """Tests for SORT_OPTIONS dict."""

    def test_has_three_options(self):
        assert len(SORT_OPTIONS) == 3

    def test_has_expected_keys(self):
        assert "name_asc" in SORT_OPTIONS
        assert "name_desc" in SORT_OPTIONS
        assert "popular" in SORT_OPTIONS

    def test_values_are_strings(self):
        for v in SORT_OPTIONS.values():
            assert isinstance(v, str)


class TestVersionPinning:
    """Tests for version pinning: save/load/remove installed versions."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_get_file = None

    def _patch_filepath(self):
        import frontend.pages._marketplace_page as mp_module
        self.original_get_file = mp_module._get_installed_versions_file
        mp_module._get_installed_versions_file = lambda: os.path.join(
            self.tmpdir, "test_installed_skills.json"
        )

    def _unpatch_filepath(self):
        if self.original_get_file:
            import frontend.pages._marketplace_page as mp_module
            mp_module._get_installed_versions_file = self.original_get_file

    def teardown_method(self):
        self._unpatch_filepath()

    def test_save_and_load_version(self):
        self._patch_filepath()
        _save_installed_version("skill_a", "1.0.0")
        versions = _load_installed_versions_for_write()
        assert versions.get("skill_a") == "1.0.0"
        self._unpatch_filepath()

    def test_save_overwrites_existing(self):
        self._patch_filepath()
        _save_installed_version("skill_b", "1.0.0")
        _save_installed_version("skill_b", "2.0.0")
        versions = _load_installed_versions_for_write()
        assert versions.get("skill_b") == "2.0.0"
        self._unpatch_filepath()

    def test_remove_existing_version(self):
        self._patch_filepath()
        _save_installed_version("skill_c", "1.5.0")
        _remove_installed_version("skill_c")
        versions = _load_installed_versions_for_write()
        assert "skill_c" not in versions
        self._unpatch_filepath()

    def test_remove_nonexistent_version_no_error(self):
        self._patch_filepath()
        _remove_installed_version("nonexistent_skill")
        versions = _load_installed_versions_for_write()
        assert versions == {}
        self._unpatch_filepath()

    def test_multiple_skills_tracked(self):
        self._patch_filepath()
        _save_installed_version("s1", "1.0.0")
        _save_installed_version("s2", "2.0.0")
        _save_installed_version("s3", "3.0.0")
        versions = _load_installed_versions_for_write()
        assert len(versions) == 3
        assert versions["s1"] == "1.0.0"
        assert versions["s2"] == "2.0.0"
        assert versions["s3"] == "3.0.0"
        self._unpatch_filepath()

    def test_persists_to_disk_json_format(self):
        self._patch_filepath()
        filepath = os.path.join(self.tmpdir, "test_installed_skills.json")
        _save_installed_version("disk_test", "4.2.0")
        assert os.path.exists(filepath)
        with open(filepath, "r") as f:
            data = json.load(f)
        assert data == {"disk_test": "4.2.0"}
        self._unpatch_filepath()

    def test_load_empty_when_no_file(self):
        self._patch_filepath()
        versions = _load_installed_versions_for_write()
        assert versions == {}
        self._unpatch_filepath()


class TestSkillDetailDataPrep:
    """Tests for detail view data extraction from skill dicts."""

    def test_extract_fields_from_complete_skill(self):
        skill = SAMPLE_SKILLS[0]
        assert skill["skill_id"] == "crm_pro"
        assert skill["name"] == "CRM Pro"
        assert skill["version"] == "2.1.0"
        assert skill["category"] == "CRM"
        assert skill["author"] == "OPC Team"
        assert skill["tags"] == ["sales", "customer"]

    def test_default_values_for_missing_fields(self):
        partial = {"skill_id": "minimal"}
        assert partial.get("name", "未知技能") == "未知技能"
        assert partial.get("version", "1.0.0") == "1.0.0"
        assert partial.get("category", "general") == "general"
        assert partial.get("author", "OPC-Agents Team") == "OPC-Agents Team"
        assert partial.get("tags", []) == []

    def test_update_available_detection(self):
        installed_versions = {"crm_pro": "1.0.0"}
        skill = SAMPLE_SKILLS[0]
        is_installed = skill["skill_id"] in installed_versions
        installed_ver = installed_versions.get(skill["skill_id"], "")
        update_available = is_installed and installed_ver and installed_ver != skill["version"]
        assert is_installed is True
        assert update_available is True

    def test_no_update_when_same_version(self):
        installed_versions = {"finance_tracker": "1.5.0"}
        skill = SAMPLE_SKILLS[1]
        installed_ver = installed_versions.get(skill["skill_id"], "")
        update_available = (skill["skill_id"] in installed_versions
                           and installed_ver
                           and installed_ver != skill["version"])
        assert update_available is False

    def test_not_installed_detection(self):
        installed_versions = {}
        skill = SAMPLE_SKILLS[2]
        is_installed = skill["skill_id"] in installed_versions
        assert is_installed is False
