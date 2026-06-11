import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar, get_type_hints

from pydantic import BaseModel

from fsq_agent.models import (
    ANDROID_ACTION_DEFINITIONS_BY_NAME,
    ConfigurationError,
    HarnessFunctionSchema,
    HarnessPlatform,
)


_F = TypeVar("_F", bound=Callable[..., Any])
_DRIVER_TOOL_METADATA_ATTR = "__fsq_driver_tool__"


@dataclass(frozen=True)
class _DriverToolMetadata:
    description: str
    params_model: type[BaseModel] | None = None
    fsq_action_name: str | None = None
    strict: bool = True
    metadata: dict[str, object] = field(default_factory=dict)


def driver_tool(
    *,
    description: str,
    params_model: type[BaseModel] | None = None,
    fsq_action_name: str | None = None,
    strict: bool = True,
    metadata: dict[str, object] | None = None,
) -> Callable[[_F], _F]:
    def decorate(method: _F) -> _F:
        setattr(
            method,
            _DRIVER_TOOL_METADATA_ATTR,
            _DriverToolMetadata(
                description=description,
                params_model=params_model,
                fsq_action_name=fsq_action_name,
                strict=strict,
                metadata=dict(metadata or {}),
            ),
        )
        return method

    return decorate


def _android_driver_tool(
    fsq_action_name: str,
    *,
    description: str,
    strict: bool = True,
    metadata: dict[str, object] | None = None,
) -> Callable[[_F], _F]:
    action_definition = ANDROID_ACTION_DEFINITIONS_BY_NAME.get(fsq_action_name)
    if action_definition is None:
        raise ConfigurationError(
            "Unknown Android driver tool action.",
            context={"fsq_action_name": fsq_action_name},
        )

    def decorate(method: _F) -> _F:
        method_name = getattr(method, "__name__", "")
        if method_name != action_definition.driver_method:
            raise ConfigurationError(
                "Android driver tool method does not match the action registry.",
                context={
                    "fsq_action_name": fsq_action_name,
                    "expected_method": action_definition.driver_method,
                    "actual_method": method_name,
                },
            )
        try:
            hints = get_type_hints(method)
        except Exception as exc:
            raise ConfigurationError(
                "Android driver tool parameter model could not be resolved.",
                context={"method": method_name, "reason": str(exc)},
            ) from exc
        annotated_model = hints.get("params")
        if annotated_model is not action_definition.params_model:
            raise ConfigurationError(
                "Android driver tool parameter model does not match the action registry.",
                context={
                    "fsq_action_name": fsq_action_name,
                    "method": method_name,
                    "expected_model": action_definition.params_model.__name__,
                    "actual_model": getattr(annotated_model, "__name__", str(annotated_model)),
                },
            )
        return driver_tool(
            description=description,
            params_model=action_definition.params_model,
            fsq_action_name=action_definition.fsq_action_name,
            strict=strict,
            metadata=metadata,
        )(method)

    return decorate


def _discover_driver_function_schemas(
    driver: object,
    *,
    platform: HarnessPlatform,
    metadata: dict[str, object] | None = None,
) -> list[HarnessFunctionSchema]:
    schemas: list[HarnessFunctionSchema] = []
    for method_name, method in inspect.getmembers(type(driver), predicate=callable):
        tool_metadata = getattr(method, _DRIVER_TOOL_METADATA_ATTR, None)
        if not isinstance(tool_metadata, _DriverToolMetadata):
            continue
        params_model = tool_metadata.params_model or _infer_params_model(method_name, method)
        schema_metadata = dict(metadata or {})
        schema_metadata.update(tool_metadata.metadata)
        schemas.append(
            HarnessFunctionSchema(
                name=method_name,
                description=tool_metadata.description,
                params_json_schema=params_model.model_json_schema(),
                strict=tool_metadata.strict,
                platform=platform,
                driver_method=method_name,
                fsq_action_name=tool_metadata.fsq_action_name,
                metadata=schema_metadata,
            )
        )
    return schemas


def _infer_params_model(method_name: str, method: Callable[..., Any]) -> type[BaseModel]:
    try:
        hints = get_type_hints(method)
    except Exception as exc:
        raise ConfigurationError(
            "Driver tool parameter model could not be resolved.",
            context={"method": method_name, "reason": str(exc)},
        ) from exc

    model = hints.get("params")
    if isinstance(model, type) and issubclass(model, BaseModel):
        return model
    raise ConfigurationError(
        "Driver tool requires a Pydantic params model annotation or explicit params_model.",
        context={"method": method_name},
    )