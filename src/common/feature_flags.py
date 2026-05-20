# flake8: noqa: E501
"""Feature flag rollout validation helpers.

The deployment path uses these helpers to validate a rendered production
configuration against a small, explicit manifest of required feature flags
before traffic is shifted to scheduler/worker services.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from src.common.errors import ConfigurationError

DEFAULT_FLAG_PATHS = (
    ("feature_flags",),
    ("features",),
    ("flags",),
)


@dataclass(frozen=True)
class RequiredFeatureFlag:
    """A feature flag that must be present and consistent during rollout."""

    name: str
    default: Any
    owner: str
    services: Sequence[str]
    required: bool = True

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], default_services: Sequence[str]) -> "RequiredFeatureFlag":
        name = raw.get("name")
        owner = raw.get("owner")
        if not isinstance(name, str) or not name:
            raise ConfigurationError(
                "feature flag manifest entries must include a non-empty name")
        if "default" not in raw:
            raise ConfigurationError(
                f"feature flag {name!r} must document a default value")
        if not isinstance(owner, str) or not owner:
            raise ConfigurationError(
                f"feature flag {name!r} must document an owner")

        services = raw.get("services", default_services)
        if not isinstance(services, Sequence) or isinstance(services, (str, bytes)) or not services:
            raise ConfigurationError(
                f"feature flag {name!r} must declare at least one service")
        if not all(isinstance(service, str) and service for service in services):
            raise ConfigurationError(
                f"feature flag {name!r} services must be non-empty strings")

        return cls(
            name=name,
            default=raw["default"],
            owner=owner,
            services=tuple(services),
            required=bool(raw.get("required", True)),
        )


@dataclass(frozen=True)
class FeatureFlagManifest:
    """Required feature flags and service scopes for a deployment."""

    flags: Sequence[RequiredFeatureFlag]
    services: Sequence[str]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "FeatureFlagManifest":
        services = raw.get("services", ("scheduler", "worker"))
        if not isinstance(services, Sequence) or isinstance(services, (str, bytes)) or not services:
            raise ConfigurationError(
                "feature flag manifest must declare at least one service")
        if not all(isinstance(service, str) and service for service in services):
            raise ConfigurationError(
                "feature flag manifest services must be non-empty strings")

        raw_flags = raw.get("flags")
        if not isinstance(raw_flags, Sequence) or isinstance(raw_flags, (str, bytes)) or not raw_flags:
            raise ConfigurationError(
                "feature flag manifest must contain at least one flag")

        flags = tuple(RequiredFeatureFlag.from_dict(
            flag, tuple(services)) for flag in raw_flags)
        return cls(flags=flags, services=tuple(services))

    @classmethod
    def load(cls, path: str) -> "FeatureFlagManifest":
        with open(path) as f:
            return cls.from_dict(json.load(f))


def validate_feature_flag_rollout(
    rendered_config: Mapping[str, Any],
    manifest: FeatureFlagManifest,
) -> None:
    """Fail closed unless required feature flags are ready for rollout.

    The validator checks all manifest-required flags before deployment can
    proceed. It deliberately reports only flag and service names, never the
    rendered values, because flags may gate sensitive operational behavior.
    """

    missing: List[str] = []
    mismatched: List[str] = []

    for flag in manifest.flags:
        if not flag.required:
            continue

        observed: Dict[str, Any] = {}
        for service in flag.services:
            found, value = _service_flag_value(
                rendered_config, service, flag.name)
            if not found:
                missing.append(f"{flag.name} for {service}")
                continue
            observed[service] = value

        if observed and any(value != flag.default for value in observed.values()):
            mismatched.append(f"{flag.name} default differs from manifest")
        if len(observed) > 1 and len({json.dumps(value, sort_keys=True) for value in observed.values()}) > 1:
            mismatched.append(
                f"{flag.name} differs across services: {', '.join(sorted(observed))}")

    if missing or mismatched:
        details = []
        if missing:
            details.append("missing required flags: " +
                           "; ".join(sorted(missing)))
        if mismatched:
            details.append("inconsistent required flags: " +
                           "; ".join(sorted(set(mismatched))))
        raise ConfigurationError(
            "feature flag rollout validation failed; " + " | ".join(details))


def validate_feature_flag_rollout_from_files(rendered_config_path: str, manifest_path: str) -> None:
    """Validate rendered config and manifest JSON files for deploy commands."""

    with open(rendered_config_path) as f:
        rendered_config = json.load(f)
    validate_feature_flag_rollout(
        rendered_config, FeatureFlagManifest.load(manifest_path))


def _service_flag_value(config: Mapping[str, Any], service: str, flag_name: str) -> tuple[bool, Optional[Any]]:
    service_config = _service_config(config, service)
    if not isinstance(service_config, Mapping):
        return False, None

    for flag_path in DEFAULT_FLAG_PATHS:
        flag_container = _nested_get(service_config, flag_path)
        if isinstance(flag_container, Mapping) and flag_name in flag_container:
            return True, flag_container[flag_name]
    return False, None


def _service_config(config: Mapping[str, Any], service: str) -> Optional[Mapping[str, Any]]:
    services = config.get("services")
    if isinstance(services, Mapping) and isinstance(services.get(service), Mapping):
        return services[service]
    if isinstance(config.get(service), Mapping):
        return config[service]  # type: ignore[index]
    return None


def _nested_get(config: Mapping[str, Any], path: Iterable[str]) -> Optional[Any]:
    current: Any = config
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current
