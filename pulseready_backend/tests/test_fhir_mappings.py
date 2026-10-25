import copy

import pytest

from app.fhir import build_synthetic_resources
from app.mappings import map_fhir_resource


def test_versioned_observation_mapping_is_stable_and_minimal():
    observation = build_synthetic_resources()[1]
    expected = {
        "facility_code": "A-01",
        "signal_type": "heart_rate",
        "observed_at": "2026-10-23T10:00:00Z",
        "value": 72.0,
        "unit": "/min",
        "source": "fhir-r4-synthetic",
    }
    assert map_fhir_resource(observation, "fhir_observation.json") == expected
    assert map_fhir_resource(copy.deepcopy(observation), "fhir_observation.json") == expected


def test_patient_mapping_only_returns_a_synthetic_reference():
    assert map_fhir_resource({"resourceType": "Patient", "id": "synthetic-patient-001"}, "fhir_patient.json") == {
        "patient_reference": "Patient/synthetic-patient-001"
    }


@pytest.mark.parametrize("resource", [
    {"resourceType": "Patient"},
    {"resourceType": "Observation", "effectiveDateTime": None},
    {"resourceType": "Other", "id": "x"},
])
def test_mapping_rejects_missing_null_or_unsupported_inputs(resource):
    mapping = "fhir_patient.json" if resource.get("resourceType") == "Patient" else "fhir_observation.json"
    with pytest.raises(ValueError):
        map_fhir_resource(resource, mapping)


def test_mapping_name_is_allowlisted():
    with pytest.raises(ValueError):
        map_fhir_resource({}, "../../etc/passwd")
