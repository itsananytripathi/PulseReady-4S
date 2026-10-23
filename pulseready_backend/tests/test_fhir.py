import copy

import pytest

from app.fhir import build_synthetic_resources, validate_fhir_r4_resource


def test_synthetic_fhir_r4_resources_validate_and_reference_correctly():
    resources = build_synthetic_resources()
    assert [resource["resourceType"] for resource in resources] == [
        "Location", "Observation", "SupplyDelivery"
    ]
    assert all(validate_fhir_r4_resource(resource) for resource in resources)
    location, observation, supply_delivery = resources
    assert observation["subject"]["reference"].startswith("Patient/")
    assert supply_delivery["destination"]["reference"] == f"Location/{location['id']}"
    assert observation["valueQuantity"]["code"] == "/min"
    assert supply_delivery["suppliedItem"]["quantity"]["code"] == "{box}"


@pytest.mark.parametrize("resource_index, mutation", [
    (0, lambda resource: resource.pop("status")),
    (1, lambda resource: resource["valueQuantity"].update({"code": "kg"})),
    (2, lambda resource: resource["destination"].update({"reference": "Patient/wrong"})),
])
def test_invalid_synthetic_fhir_payloads_are_rejected(resource_index, mutation):
    resource = copy.deepcopy(build_synthetic_resources()[resource_index])
    mutation(resource)
    with pytest.raises(ValueError):
        validate_fhir_r4_resource(resource)


def test_unknown_fhir_resource_type_is_rejected():
    with pytest.raises(ValueError):
        validate_fhir_r4_resource({"resourceType": "Patient", "id": "synthetic-patient-001"})
