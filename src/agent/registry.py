"""Agent registry with auth-aware resolution."""

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"
    TERMINATED = "terminated"


class AgentRegistry:
    def __init__(self, storage_backend: str = "memory"):
        self.storage_backend = storage_backend
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, List[str]] = {}
        self._auth_policies: Dict[str, Dict[str, bool]] = {}
        self._auth_versions: Dict[str, int] = {}
        self._resolution_cache: Dict[
            Tuple[str, str, str], Dict[str, Any]
        ] = {}
        self._audit_log: List[Dict[str, Any]] = []

    def register(
        self,
        name: str,
        agent_type: str,
        config: Optional[Dict] = None,
    ) -> str:
        agent_id = str(uuid.uuid4())
        timestamp = time.time()
        self._agents[agent_id] = {
            "id": agent_id,
            "name": name,
            "type": agent_type,
            "status": AgentStatus.PENDING.value,
            "config": config or {},
            "created_at": timestamp,
            "updated_at": timestamp,
            "version": "1.0.0",
            "metrics": {
                "tasks_completed": 0,
                "errors": 0,
                "uptime": 0,
            },
        }
        group = agent_type.split(".")[0]
        if group not in self._index:
            self._index[group] = []
        self._index[group].append(agent_id)
        self._auth_policies[agent_id] = {}
        self._auth_versions[agent_id] = 0
        return agent_id

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(agent_id)

    def list(
        self,
        status: Optional[AgentStatus] = None,
        group: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        agents = self._agents.values()
        if status:
            agents = [a for a in agents if a["status"] == status.value]
        if group:
            agent_ids = self._index.get(group, [])
            agents = [a for a in agents if a["id"] in agent_ids]
        return list(agents)

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        if agent_id not in self._agents:
            return False
        self._agents[agent_id]["status"] = status.value
        self._agents[agent_id]["updated_at"] = time.time()
        return True

    def set_authorization(
        self,
        agent_id: str,
        principal: str,
        role: str,
        allowed: bool,
    ) -> bool:
        """Set the current authorization policy for an agent resolution.

        Updating permissions bumps an agent-local auth version and invalidates
        all cached resolutions for that agent. Cached callers therefore cannot
        keep using a stale allowed decision after a role is revoked or changed.
        """
        if agent_id not in self._agents:
            return False
        policy_key = self._policy_key(principal, role)
        self._auth_policies.setdefault(agent_id, {})[policy_key] = allowed
        self._auth_versions[agent_id] = (
            self._auth_versions.get(agent_id, 0) + 1
        )
        self._invalidate_resolution_cache(agent_id)
        self._audit(agent_id, "permission_updated", policy_key,
                    allowed=allowed)
        return True

    def resolve_authorized(
        self,
        agent_id: str,
        principal: str,
        role: str,
    ) -> Optional[Dict[str, Any]]:
        """Resolve an agent only after rechecking current authorization.

        The registry keeps a small resolution cache. Each cache hit is tied to
        the current authorization version and is revalidated against the live
        permission policy. If permissions changed, the stale cache entry is
        discarded and the agent lifecycle state is left untouched.
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        policy_key = self._policy_key(principal, role)
        cache_key = (agent_id, principal, role)
        current_version = self._auth_versions.get(agent_id, 0)
        cached = self._resolution_cache.get(cache_key)

        if cached and cached.get("auth_version") == current_version:
            if self._is_authorized(agent_id, policy_key):
                self._audit(agent_id, "cache_allowed", policy_key)
                return cached["agent"]
            self._resolution_cache.pop(cache_key, None)
            self._audit(agent_id, "cache_denied", policy_key)
            return None

        if cached:
            self._resolution_cache.pop(cache_key, None)
            self._audit(agent_id, "cache_invalidated", policy_key)

        if not self._is_authorized(agent_id, policy_key):
            self._audit(agent_id, "resolution_denied", policy_key)
            return None

        self._resolution_cache[cache_key] = {
            "agent": agent,
            "auth_version": current_version,
            "resolved_at": time.time(),
        }
        self._audit(agent_id, "resolution_allowed", policy_key)
        return agent

    def audit_log(self) -> List[Dict[str, Any]]:
        """Return sanitized authorization decisions for diagnostics."""
        return list(self._audit_log)

    def delete(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        agent = self._agents.pop(agent_id)
        group = agent["type"].split(".")[0]
        if group in self._index and agent_id in self._index[group]:
            self._index[group].remove(agent_id)
        self._auth_policies.pop(agent_id, None)
        self._auth_versions.pop(agent_id, None)
        self._invalidate_resolution_cache(agent_id)
        return True

    def count(self) -> int:
        return len(self._agents)

    def _is_authorized(self, agent_id: str, policy_key: str) -> bool:
        return self._auth_policies.get(agent_id, {}).get(policy_key, False)

    def _policy_key(self, principal: str, role: str) -> str:
        return f"{principal}:{role}"

    def _invalidate_resolution_cache(self, agent_id: str) -> None:
        stale_keys = [
            key for key in self._resolution_cache if key[0] == agent_id
        ]
        for key in stale_keys:
            self._resolution_cache.pop(key, None)

    def _audit(
        self,
        agent_id: str,
        event: str,
        policy_key: str,
        **extra: Any,
    ) -> None:
        self._audit_log.append({
            "agent_id": agent_id,
            "event": event,
            "policy": policy_key,
            "timestamp": time.time(),
            **extra,
        })

# 2019-01-29T11:24:49 update
# 2019-04-09T13:38:38 update
# 2019-04-11T11:24:12 update
# 2019-06-26T17:03:48 update
# 2019-07-03T14:55:48 update
# 2019-07-18T18:18:47 update
# 2019-11-05T11:27:19 update
# 2019-11-20T11:35:05 update
# 2019-11-23T15:28:54 update
# 2020-03-13T09:23:07 update
# 2020-03-30T19:31:18 update
# 2020-04-22T15:03:30 update
# 2020-07-21T10:00:48 update
# 2020-09-10T09:02:08 update
# 2020-09-10T13:39:12 update
# 2020-09-22T16:27:52 update
# 2020-10-15T10:33:14 update
# 2021-05-13T11:15:56 update
# 2021-07-07T14:57:13 update
# 2021-07-13T15:15:19 update
# 2021-07-27T10:18:16 update
# 2022-03-11T15:24:11 update
# 2022-09-22T13:24:20 update
# 2022-11-01T12:20:40 update
# 2023-01-30T12:32:27 update
# 2023-03-10T09:43:50 update
# 2023-05-10T14:28:01 update
# 2023-05-11T20:04:46 update
# 2023-05-30T17:00:59 update
# 2023-07-13T17:54:32 update
# 2023-07-20T19:04:20 update
# 2023-07-31T17:00:02 update
# 2023-09-05T19:42:07 update
# 2024-01-02T10:29:47 update
# 2024-09-17T12:45:29 update
# 2024-09-17T11:51:01 update
# 2024-11-06T18:20:15 update
# 2025-01-12T15:13:14 update
# 2025-01-14T20:24:39 update
# 2025-03-26T20:21:27 update
# 2025-04-10T18:27:06 update
# 2025-06-19T20:34:58 update
# 2025-06-21T20:23:53 update
# 2025-06-24T20:30:30 update
# 2025-07-03T13:28:03 update
# 2025-07-24T17:42:21 update
# 2025-08-19T17:42:23 update
# 2025-08-21T11:06:52 update
# 2025-10-24T09:10:08 update
# 2025-12-18T19:34:38 update
# 2026-02-06T11:22:22 update
# 2026-02-13T15:42:04 update
# 2026-04-10T08:16:30 update
# 2026-04-29T18:16:11 update
