"""Small, local FHIR R4 example/shape validator for synthetic interoperability tests.

This is deliberately not a complete FHIR validator or terminology server. It
checks the fields and references used by the synthetic examples only.
"""

from datetime import datetime
from numbers import Real


FHIR_R4_VERSION = "4.0.1"
LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"
SUPPLY_TYPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/supply-item-type"
SYNTHETIC_SUPPLY_SYSTEM = "https://pulseready.example/fhir/CodeSystem/synthetic-supply-item"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _reference(resource, prefix):
    reference = resource.get("reference") if isinstance(resource, dict) else None
    _require(isinstance(reference, str) and reference.startswith(f"{prefix}/"),
             f"reference must start with {prefix}/")


def _coding(codeable_concept):
    codings = codeable_concept.get("coding") if isinstance(codeable_concept, dict) else None
    _require(isinstance(codings, list) and codings, "codeable concept requires coding")
    return codings[0]


def _validate_location(resource):
    _require(resource.get("status") in {"active", "suspended", "inactive", "entered-in-error"},
             "Location.status is invalid")
    _require(isinstance(resource.get("name"), str) and resource["name"],
             "Location.name is required for this synthetic example")


def _validate_observation(resource):
    _require(resource.get("status") in {"registered", "preliminary", "final", "amended", "corrected", "cancelled", "entered-in-error", "unknown"},
             "Observation.status is invalid")
    code = _coding(resource.get("code", {}))
    _require(code.get("system") == LOINC_SYSTEM and code.get("code") == "8867-4",
             "Observation.code must be LOINC heart rate 8867-4")
    _reference(resource.get("subject", {}), "Patient")
    try:
        datetime.fromisoformat(resource["effectiveDateTime"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Observation.effectiveDateTime must be ISO-8601") from exc
    quantity = resource.get("valueQuantity", {})
    _require(isinstance(quantity.get("value"), Real) and not isinstance(quantity.get("value"), bool),
             "Observation.valueQuantity.value must be numeric")
    _require(quantity.get("unit") == "beats/minute" and quantity.get("system") == UCUM_SYSTEM and quantity.get("code") == "/min",
             "Observation value must use the beats/minute UCUM representation")


def _validate_supply_delivery(resource):
    _require(resource.get("status") in {"in-progress", "completed", "abandoned", "entered-in-error"},
             "SupplyDelivery.status is invalid")
    supply_type = _coding(resource.get("type", {}))
    _require(supply_type.get("system") == SUPPLY_TYPE_SYSTEM and supply_type.get("code") == "device",
             "SupplyDelivery.type must use the R4 device supply type")
    supplied = resource.get("suppliedItem", {})
    quantity = supplied.get("quantity", {})
    _require(isinstance(quantity.get("value"), Real) and quantity.get("value") > 0,
             "SupplyDelivery quantity must be positive")
    _require(quantity.get("unit") == "box" and quantity.get("system") == UCUM_SYSTEM and quantity.get("code") == "{box}",
             "SupplyDelivery quantity must use the synthetic box UCUM representation")
    item = _coding(supplied.get("itemCodeableConcept", {}))
    _require(item.get("system") == SYNTHETIC_SUPPLY_SYSTEM and item.get("code") == "synthetic-nitrile-gloves",
             "SupplyDelivery item must use the declared synthetic supply code system")
    try:
        datetime.fromisoformat(resource["occurrenceDateTime"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError("SupplyDelivery.occurrenceDateTime must be ISO-8601") from exc
    _reference(resource.get("destination", {}), "Location")


def validate_fhir_r4_resource(resource):
    _require(isinstance(resource, dict), "FHIR resource must be an object")
    resource_type = resource.get("resourceType")
    _require(resource_type in {"Location", "Observation", "SupplyDelivery"},
             "unsupported synthetic FHIR R4 resource type")
    _require(isinstance(resource.get("id"), str) and resource["id"], "FHIR resource id is required")
    if resource_type == "Location":
        _validate_location(resource)
    elif resource_type == "Observation":
        _validate_observation(resource)
    else:
        _validate_supply_delivery(resource)
    return True


def build_synthetic_resources():
    location = {
        "resourceType": "Location",
        "id": "synthetic-location-a01",
        "status": "active",
        "name": "Synthetic PulseReady Facility A-01",
    }
    observation = {
        "resourceType": "Observation",
        "id": "synthetic-heart-rate-001",
        "status": "final",
        "code": {
            "coding": [{"system": LOINC_SYSTEM, "code": "8867-4", "display": "Heart rate"}],
            "text": "Heart rate",
        },
        "subject": {"reference": "Patient/synthetic-patient-001"},
        "effectiveDateTime": "2026-10-23T10:00:00Z",
        "valueQuantity": {
            "value": 72,
            "unit": "beats/minute",
            "system": UCUM_SYSTEM,
            "code": "/min",
        },
    }
    supply_delivery = {
        "resourceType": "SupplyDelivery",
        "id": "synthetic-supply-delivery-001",
        "status": "completed",
        "type": {
            "coding": [{"system": SUPPLY_TYPE_SYSTEM, "code": "device", "display": "Device"}]
        },
        "suppliedItem": {
            "quantity": {"value": 100, "unit": "box", "system": UCUM_SYSTEM, "code": "{box}"},
            "itemCodeableConcept": {
                "coding": [{
                    "system": SYNTHETIC_SUPPLY_SYSTEM,
                    "code": "synthetic-nitrile-gloves",
                    "display": "Synthetic nitrile examination gloves",
                }]
            },
        },
        "occurrenceDateTime": "2026-10-23T10:00:00Z",
        "destination": {"reference": "Location/synthetic-location-a01"},
    }
    return [location, observation, supply_delivery]
