from fsq_agent.core.harness._driver_tools import _discover_driver_capability_definitions
from fsq_agent.core.harness._uiautomator2_driver import UiAutomator2AndroidDriver
from fsq_agent.models import AndroidAssertWithAIParams, CapabilityDefinition, ReplayPolicy


def android_capability_definitions(*, include_ai_assertion: bool = True) -> list[CapabilityDefinition]:
    metadata: dict[str, object] = {"driver_class": UiAutomator2AndroidDriver.__name__, "backend": UiAutomator2AndroidDriver.backend}
    definitions = _discover_driver_capability_definitions(
        UiAutomator2AndroidDriver,
        platform="android",
        metadata=metadata,
    )
    if include_ai_assertion:
        definitions.append(_android_assert_with_ai_capability(metadata))
    return definitions


def _android_assert_with_ai_capability(metadata: dict[str, object]) -> CapabilityDefinition:
    capability_metadata = dict(metadata)
    capability_metadata.update({"owner": "harness", "driver_method": "assert_with_ai", "fsq_action_name": "assertWithAI"})
    return CapabilityDefinition(
        name="assert_with_ai",
        aliases=["assertWithAI"],
        executor_kind="harness",
        params_model=AndroidAssertWithAIParams,
        step_kind="assertion",
        description="Evaluate an explicit Android visual assertion with a fresh screenshot and the configured AI evaluator.",
        platform="android",
        backend=str(metadata.get("backend")) if metadata.get("backend") else None,
        owner="harness",
        capture_evidence=False,
        replay=ReplayPolicy(kind="fsq_command", alias="assertWithAI"),
        metadata=capability_metadata,
    )
