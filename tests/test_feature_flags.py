# flake8: noqa: E501
import json

import pytest

from src.common.errors import ConfigurationError
from src.common.feature_flags import (
    FeatureFlagManifest,
    validate_feature_flag_rollout,
    validate_feature_flag_rollout_from_files,
)


class TestFeatureFlagRolloutValidation:
    def test_missing_required_flag_blocks_rollout(self):
        manifest = FeatureFlagManifest.from_dict(
            {
                "services": ["scheduler", "worker"],
                "flags": [
                    {
                        "name": "bounded_retries",
                        "default": False,
                        "owner": "runtime-platform",
                    }
                ],
            }
        )
        rendered_config = {
            "services": {
                "scheduler": {"feature_flags": {"bounded_retries": False}},
                "worker": {"feature_flags": {}},
            }
        }

        with pytest.raises(ConfigurationError) as exc_info:
            validate_feature_flag_rollout(rendered_config, manifest)

        message = str(exc_info.value)
        assert "bounded_retries for worker" in message
        assert "False" not in message

    def test_scheduler_and_worker_values_must_match_manifest_default(self):
        manifest = FeatureFlagManifest.from_dict(
            {
                "services": ["scheduler", "worker"],
                "flags": [
                    {
                        "name": "dispatch_v2",
                        "default": False,
                        "owner": "scheduler-team",
                    }
                ],
            }
        )
        rendered_config = {
            "services": {
                "scheduler": {"feature_flags": {"dispatch_v2": False}},
                "worker": {"feature_flags": {"dispatch_v2": True}},
            }
        }

        with pytest.raises(ConfigurationError) as exc_info:
            validate_feature_flag_rollout(rendered_config, manifest)

        message = str(exc_info.value)
        assert "dispatch_v2 default differs from manifest" in message
        assert "dispatch_v2 differs across services: scheduler, worker" in message
        assert "True" not in message
        assert "False" not in message

    def test_documented_defaults_and_owners_allow_rollout(self):
        manifest = FeatureFlagManifest.from_dict(
            {
                "services": ["scheduler", "worker"],
                "flags": [
                    {
                        "name": "dispatch_v2",
                        "default": False,
                        "owner": "scheduler-team",
                    },
                    {
                        "name": "worker_idempotency_guard",
                        "default": True,
                        "owner": "worker-team",
                        "services": ["worker"],
                    },
                ],
            }
        )
        rendered_config = {
            "services": {
                "scheduler": {"feature_flags": {"dispatch_v2": False}},
                "worker": {
                    "feature_flags": {
                        "dispatch_v2": False,
                        "worker_idempotency_guard": True,
                    }
                },
            }
        }

        validate_feature_flag_rollout(rendered_config, manifest)

    def test_manifest_file_validation_is_available_for_deploy_path(self, tmp_path):
        manifest_path = tmp_path / "feature-flags.json"
        rendered_path = tmp_path / "rendered-config.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "services": ["scheduler", "worker"],
                    "flags": [
                        {
                            "name": "safe_rollout_mode",
                            "default": "monitor",
                            "owner": "release-team",
                        }
                    ],
                }
            )
        )
        rendered_path.write_text(
            json.dumps(
                {
                    "services": {
                        "scheduler": {"feature_flags": {"safe_rollout_mode": "monitor"}},
                        "worker": {"feature_flags": {"safe_rollout_mode": "monitor"}},
                    }
                }
            )
        )

        validate_feature_flag_rollout_from_files(
            str(rendered_path), str(manifest_path))

    def test_manifest_requires_documented_default_and_owner(self):
        with pytest.raises(ConfigurationError) as exc_info:
            FeatureFlagManifest.from_dict(
                {
                    "flags": [
                        {
                            "name": "new_scheduler_path",
                            "owner": "scheduler-team",
                        }
                    ]
                }
            )

        assert "must document a default value" in str(exc_info.value)

    def test_malformed_manifest_entries_raise_configuration_error(self):
        with pytest.raises(ConfigurationError, match="entries must be objects"):
            FeatureFlagManifest.from_dict(
                {
                    "services": ["scheduler", "worker"],
                    "flags": ["dispatch_v2"],
                }
            )

    def test_manifest_root_must_be_object(self):
        with pytest.raises(ConfigurationError, match="manifest must be an object"):
            FeatureFlagManifest.from_dict(["not", "an", "object"])  # type: ignore[arg-type]
