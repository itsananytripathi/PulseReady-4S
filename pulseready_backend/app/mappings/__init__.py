"""Safe, repository-controlled declarative FHIR mapping helpers."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


MAPPING_DIR = Path(__file__).parent


class OperationalSignalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facility_code: str = Field(min_length=1, max_length=80)
    signal_type: str = Field(min_length=1, max_length=100)
    observed_at: str
    value: float
    unit: str = "count"
    source: str = "fhir-r4"


def _path_get(document: dict[str, Any], path: str) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"missing mapping path: {path}")
        current = current[part]
    if current is None:
        raise ValueError(f"null mapping path: {path}")
    return current


def load_mapping(mapping_name: str) -> dict[str, Any]:
    if mapping_name not in {"fhir_observation.json", "fhir_patient.json"}:
        raise ValueError("unsupported mapping")
    path = MAPPING_DIR / mapping_name
    try:
        definition = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("malformed mapping definition") from exc
    if not isinstance(definition, dict) or not definition.get("mapping_id") or not isinstance(definition.get("fields"), dict):
        raise ValueError("malformed mapping definition")
    return definition


def map_fhir_resource(resource: dict[str, Any], mapping_name: str) -> dict[str, Any]:
    definition = load_mapping(mapping_name)
    if not isinstance(resource, dict) or resource.get("resourceType") != definition.get("source_resource_type"):
        raise ValueError("unsupported resource type for mapping")
    result: dict[str, Any] = {}
    for target, spec in definition["fields"].items():
        if "constant" in spec:
            result[target] = spec["constant"]
        else:
            result[target] = _path_get(resource, spec["path"])
            if spec.get("prefix"):
                result[target] = f"{spec['prefix']}{result[target]}"
    if mapping_name == "fhir_observation.json":
        try:
            return OperationalSignalRecord.model_validate(result).model_dump()
        except ValidationError as exc:
            raise ValueError(f"mapped signal failed validation: {exc.errors()[0]['msg']}") from exc
    patient_id = result.get("patient_reference", "")
    if not isinstance(patient_id, str) or not patient_id.startswith("Patient/"):
        raise ValueError("patient mapping requires a synthetic Patient reference")
    return {"patient_reference": patient_id}
