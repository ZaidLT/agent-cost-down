from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def canonical(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Verdict(StrEnum):
    ACCEPT = "ACCEPT"
    RETRY = "RETRY"
    CLARIFY = "CLARIFY"
    UNRESOLVED = "UNRESOLVED"


JsonType = Literal["string", "integer", "number", "boolean", "object", "array", "null"]


class Observation(Contract):
    code: Literal[
        "INVALID_JSON",
        "INVALID_ARGUMENT_TYPE",
        "MISSING_REQUIRED_FIELD",
        "UNKNOWN_TOOL",
        "BUSINESS_RULE_VIOLATION",
        "STEP_LIMIT",
    ]
    tool: (
        Literal[
            "search_products",
            "list_orders",
            "get_order",
            "check_stock",
            "get_rules",
            "read_only_sql",
            "submit_draft",
            "submit_answer",
            "clarify",
            "refuse",
            "reserve_inventory",
        ]
        | None
    )
    field: str | None = Field(max_length=128)
    expected_type: JsonType | None
    observed_type: JsonType | None


class FailureContext(Contract):
    schema_version: Literal[1]
    source_model: str = Field(max_length=200)
    attempt_number: Literal[1]
    restart_from_original_state: Literal[True]
    reason: Literal[
        "parse_failed", "tool_schema_failed", "runtime_validation_failed", "attempt_budget_exhausted"
    ]
    observations: list[Observation] = Field(min_length=1, max_length=3)

    @model_validator(mode="before")
    @classmethod
    def exact_literal_types(cls, value):
        if isinstance(value, dict):
            for key in ("schema_version", "attempt_number"):
                if key in value and type(value[key]) is not int:
                    raise ValueError("Context version and attempt must be integer 1")
            if (
                "restart_from_original_state" in value
                and type(value["restart_from_original_state"]) is not bool
            ):
                raise ValueError("Restart must be boolean true")
        return value

    @model_validator(mode="after")
    def bounded(self):
        if len(canonical(self).encode()) > 2048:
            raise ValueError("FailureContext exceeds 2 KB")
        return self


class PublicTask(Contract):
    schema_version: Literal[1] = 1
    id: str
    adapter: Literal["orders", "inventory"] = "orders"
    family: str
    split: Literal["development", "heldout", "demo"]
    template_group: str
    request: str = Field(max_length=4000)
    customer_id: str
    as_of: str
    snapshot: str
    snapshot_hash: str
    rules: dict[str, Any]


class Limits(Contract):
    model_steps: int = Field(default=8, ge=1, le=8)
    tool_calls: int = Field(default=20, ge=1, le=20)
    deadline_seconds: int = Field(default=180, ge=1, le=600)
    output_tokens: int = Field(default=4096, ge=128, le=8192)
    request_bytes: int = Field(default=32768, ge=1024, le=65536)
    transport_retries: int = Field(default=2, ge=0, le=2)


class ModelSpec(Contract):
    id: str
    input_usd_per_million: float = Field(ge=0)
    output_usd_per_million: float = Field(ge=0)
    settings: dict[str, Any] = Field(default_factory=dict)


class ModelCatalog(Contract):
    verified_at: str
    price_source: str
    models: dict[str, ModelSpec]
    rpm: int = Field(ge=1)
    tpm: int = Field(ge=1)

    @model_validator(mode="after")
    def roles(self):
        if set(self.models) != {"small", "super", "ultra"}:
            raise ValueError("Exactly small, super and ultra models are required")
        allowed = {"temperature", "top_p", "seed", "reasoning_effort"}
        if any(set(m.settings) - allowed for m in self.models.values()):
            raise ValueError("Model settings may not override tools, messages, model, or token limits")
        return self


POLICIES = {
    "small_only": ["small"],
    "super_only": ["super"],
    "ultra_only": ["ultra"],
    "small_retry": ["small", "small"],
    "small_ultra": ["small", "ultra"],
}


class PolicyConfig(Contract):
    schema_version: Literal[1] = 1
    id: str
    adapter: Literal["orders", "inventory"] = "orders"
    models: list[ModelSpec] = Field(min_length=1, max_length=2)
    limits: Limits = Field(default_factory=Limits)
    validator_version: Literal["1"] = "1"
    parser_version: Literal["1"] = "1"
    supporting_report: str | None = None
    price_source: str
    prices_verified_at: str


def policy(catalog: ModelCatalog, policy_id: str, limits: Limits | None = None, adapter="orders"):
    return PolicyConfig(
        id=policy_id,
        adapter=adapter,
        models=[catalog.models[r] for r in POLICIES[policy_id]],
        limits=limits or Limits(),
        price_source=catalog.price_source,
        prices_verified_at=catalog.verified_at,
    )


class Usage(Contract):
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_usd: float | None = None
    duration_ms: float
    status: str
    request_id: str | None = None


class AttemptResult(Contract):
    model: str
    verdict: str
    resolution: str
    result: dict[str, Any] | None = None
    failure_context: FailureContext | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    usage: list[Usage] = Field(default_factory=list)
    normalized_calls: int = 0
    parsed_calls: int = 0
    duration_ms: float
    state_hash: str


class Outcome(Contract):
    success: bool
    critical_error: bool
    checks: dict[str, bool]


class RunRecord(Contract):
    schema_version: Literal[1] = 1
    id: str
    created_at: str
    source: Literal["live", "benchmark", "test_fixture"]
    task: PublicTask
    task_hash: str
    policy: PolicyConfig
    policy_hash: str
    repetition: int
    attempts: list[AttemptResult]
    verdict: str
    resolution: str
    outcome: Outcome | None = None
    before: dict[str, Any]
    after: dict[str, Any]
    total_estimated_usd: float | None
    measurement_complete: bool
    duration_ms: float
    elapsed_queue_ms: float = 0


class BenchmarkReport(Contract):
    schema_version: Literal[1] = 1
    id: str
    created_at: str
    source: Literal["benchmark", "test_fixture"]
    split: str
    manifest_hash: str
    provenance: dict[str, Any]
    policies: list[dict[str, Any]]
    runs: list[RunRecord]
    recommendation: dict[str, Any]
