from pathlib import Path

from fsq_agent.models import SkillConfig
from fsq_agent.skills import SkillBundle, SkillLoader


def test_skill_loader_loads_markdown_file(tmp_path: Path) -> None:
    skill_path = tmp_path / "example.md"
    skill_path.write_text("Use configured tools only.", encoding="utf-8")

    bundles = SkillLoader(tmp_path).load([SkillConfig(name="example", path=skill_path)])

    assert len(bundles) == 1
    assert isinstance(bundles[0], SkillBundle)
    assert bundles[0].name == "example"
    assert bundles[0].instructions == "Use configured tools only."
    assert bundles[0].files == [skill_path]


def test_skill_loader_returns_warning_for_missing_optional_skill(tmp_path: Path) -> None:
    bundles = SkillLoader(tmp_path).load([SkillConfig(name="missing", path=Path("missing.md"))])

    assert bundles[0].instructions == ""
    assert bundles[0].warnings


def test_repository_appium_android_skill_documents_tool_usage_recovery() -> None:
    skill_path = Path(__file__).resolve().parents[1] / "knowledge" / "skills" / "appium-android.md"

    bundles = SkillLoader(skill_path.parent).load([SkillConfig(name="appium-android", path=Path("appium-android.md"), required=True)])

    assert "Tool Selection" in bundles[0].instructions
    assert "Tool Usage Error Recovery" in bundles[0].instructions
    assert "Correct Key Examples" in bundles[0].instructions
    assert "appium_mobile_press_key" in bundles[0].instructions
    assert '"key": "BACK"' in bundles[0].instructions
    assert '"keyCode": 4' in bundles[0].instructions
    assert '"keyCode": 66' in bundles[0].instructions
    assert '"key": "ENTER"' not in bundles[0].instructions
    assert "keyCode-only" not in bundles[0].instructions
    assert "It only hides or queries the software keyboard" in bundles[0].instructions
    assert "required `pressKey` action succeeded" in bundles[0].instructions
    assert "appium_perform_actions" not in bundles[0].instructions
    assert "pointerType" not in bundles[0].instructions
