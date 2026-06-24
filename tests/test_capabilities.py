import ast
from pathlib import Path

import pytest
from pydantic import BaseModel

from fsq_agent.capabilities import (
    CapabilityActionDefinition,
    common_capability,
    discover_capability_definitions,
    platform_driver_capability,
)
from fsq_agent.core.harness._driver_tools import _discover_driver_capability_definitions
from fsq_agent.core.harness._uiautomator2_driver import UiAutomator2AndroidDriver
from fsq_agent.models import ConfigurationError, ReplayPolicy
from fsq_agent.tools import DefaultCommonToolProvider


class ExampleParams(BaseModel):
    value: str


class OtherParams(BaseModel):
    value: str


def test_common_capability_discovery_returns_serializable_definition() -> None:
    class Provider:
        @common_capability(
            name="example_tool",
            description="Example tool.",
            params_model=ExampleParams,
            aliases=["exampleTool"],
            replay=ReplayPolicy(kind="fsq_command", alias="exampleTool"),
            capture_evidence=True,
            post_action_delay_seconds=0.5,
            metadata={"origin": "test"},
        )
        async def _example_tool(self, arguments: dict[str, object]) -> object:
            raise AssertionError("discovery must not invoke the method")

    definitions = discover_capability_definitions(Provider)

    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.name == "example_tool"
    assert definition.aliases == ["exampleTool"]
    assert definition.executor_kind == "common"
    assert definition.owner == "tools"
    assert definition.capture_evidence is True
    assert definition.post_action_delay_seconds == 0.5
    assert definition.params_model is ExampleParams
    assert definition.replay == ReplayPolicy(kind="fsq_command", alias="exampleTool")
    assert definition.safe_metadata()["origin"] == "test"


def test_default_common_tool_provider_uses_shared_declaration_layer() -> None:
    definitions = {definition.name: definition for definition in DefaultCommonToolProvider.capability_definitions()}

    assert definitions["wait_ms"].aliases == ["waitMs"]
    assert definitions["wait_ms"].executor_kind == "common"
    assert definitions["wait_ms"].owner == "tools"
    assert definitions["wait_ms"].replay == ReplayPolicy(kind="fsq_command", alias="waitMs")
    assert definitions["get_runtime_secret"].sensitivity is True
    assert definitions["get_runtime_secret"].replay == ReplayPolicy(kind="dependency", alias="runtimeSecret")


def test_platform_driver_capability_validates_catalog_method_name() -> None:
    driver_action = platform_driver_capability(
        platform="android",
        backend="fake",
        catalog={
            "tapOn": CapabilityActionDefinition(
                action_name="tapOn",
                canonical_name="tap_on",
                executor_kind="driver",
                owner="driver",
                params_model=ExampleParams,
                method_name="tap_on",
                post_action_delay_seconds=0.75,
                replay=ReplayPolicy(kind="fsq_command", alias="tapOn"),
            )
        },
    )

    with pytest.raises(ConfigurationError, match="method"):
        class BadDriver:
            @driver_action("tapOn", description="Tap.")
            def wrong_name(self, params: ExampleParams) -> dict[str, object]:
                return {}


def test_platform_driver_capability_inherits_and_overrides_catalog_delay() -> None:
    driver_action = platform_driver_capability(
        platform="android",
        backend="fake",
        catalog={
            "tapOn": CapabilityActionDefinition(
                action_name="tapOn",
                canonical_name="tap_on",
                executor_kind="driver",
                owner="driver",
                params_model=ExampleParams,
                method_name="tap_on",
                post_action_delay_seconds=0.75,
                replay=ReplayPolicy(kind="fsq_command", alias="tapOn"),
            ),
            "inputText": CapabilityActionDefinition(
                action_name="inputText",
                canonical_name="input_text",
                executor_kind="driver",
                owner="driver",
                params_model=ExampleParams,
                method_name="input_text",
                post_action_delay_seconds=0.5,
                replay=ReplayPolicy(kind="fsq_command", alias="inputText"),
            ),
        },
    )

    class Driver:
        @driver_action("tapOn", description="Tap.")
        def tap_on(self, params: ExampleParams) -> dict[str, object]:
            return {}

        @driver_action("inputText", description="Input.", post_action_delay_seconds=0)
        def input_text(self, params: ExampleParams) -> dict[str, object]:
            return {}

    definitions = {definition.name: definition for definition in discover_capability_definitions(Driver)}

    assert definitions["tap_on"].post_action_delay_seconds == 0.75
    assert definitions["input_text"].post_action_delay_seconds == 0


def test_capability_rejects_negative_post_action_delay() -> None:
    with pytest.raises(ConfigurationError, match="post_action_delay_seconds"):
        class BadProvider:
            @common_capability(
                name="bad_delay",
                description="Bad.",
                params_model=ExampleParams,
                post_action_delay_seconds=-0.1,
            )
            async def bad_delay(self, arguments: dict[str, object]) -> object:
                return {}


def test_platform_driver_capability_validates_catalog_params_model() -> None:
    driver_action = platform_driver_capability(
        platform="android",
        backend="fake",
        catalog={
            "tapOn": CapabilityActionDefinition(
                action_name="tapOn",
                canonical_name="tap_on",
                executor_kind="driver",
                owner="driver",
                params_model=ExampleParams,
                method_name="tap_on",
                replay=ReplayPolicy(kind="fsq_command", alias="tapOn"),
            )
        },
    )

    with pytest.raises(ConfigurationError, match="parameter model"):
        class BadDriver:
            @driver_action("tapOn", description="Tap.")
            def tap_on(self, params: OtherParams) -> dict[str, object]:
                return {}


def test_android_driver_declarations_keep_catalog_backed_metadata() -> None:
    definitions = {
        definition.name: definition
        for definition in _discover_driver_capability_definitions(
            UiAutomator2AndroidDriver,
            platform="android",
            metadata={"driver_class": "UiAutomator2AndroidDriver", "backend": "uiautomator2"},
        )
    }

    tap = definitions["tap_on"]
    assert tap.aliases == ["tapOn"]
    assert tap.executor_kind == "driver"
    assert tap.owner == "driver"
    assert tap.platform == "android"
    assert tap.backend == "uiautomator2"
    assert tap.capture_evidence is True
    assert tap.metadata["driver_method"] == "tap_on"
    assert tap.metadata["fsq_action_name"] == "tapOn"
    assert tap.replay == ReplayPolicy(kind="fsq_command", alias="tapOn")
    assert definitions["ui_tree"].capture_evidence is False
    assert definitions["ui_tree"].step_kind == "observation"
    assert "perform_actions" not in definitions


def test_capabilities_imports_only_models_across_project_modules() -> None:
    package_root = Path(__file__).resolve().parents[1] / "fsq_agent" / "capabilities"
    forbidden = {
        "fsq_agent.agent",
        "fsq_agent.cli",
        "fsq_agent.config",
        "fsq_agent.core",
        "fsq_agent.fsq",
        "fsq_agent.knowledge",
        "fsq_agent.observation",
        "fsq_agent.playground",
        "fsq_agent.providers",
        "fsq_agent.report",
        "fsq_agent.skills",
        "fsq_agent.tools",
    }

    imports: set[str] = set()
    for source_path in package_root.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

    assert not {
        module
        for module in imports
        for forbidden_module in forbidden
        if module == forbidden_module or module.startswith(f"{forbidden_module}.")
    }
