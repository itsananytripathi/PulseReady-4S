import hashlib, json
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import AuditLog


def canonical_audit_json(
    *, tenant_id: str, actor_id: str, action: str,
    entity_type: str, entity_id: str, payload: dict,
    previous_hash: str | None,
) -> str:
    return json.dumps({
        "tenant_id": tenant_id, "actor_id": actor_id, "action": action,
        "entity_type": entity_type, "entity_id": entity_id,
        "payload": payload, "previous_hash": previous_hash
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def calculate_audit_hash(
    *, tenant_id: str, actor_id: str, action: str,
    entity_type: str, entity_id: str, payload: dict,
    previous_hash: str | None,
) -> str:
    canonical = canonical_audit_json(
        tenant_id=tenant_id, actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id, payload=payload,
        previous_hash=previous_hash,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verification_result(
    *, valid: bool, checked_count: int,
    first_invalid_event_id: str | None = None,
    failure_reason: str | None = None,
) -> dict:
    return {
        "valid": valid,
        "checked_count": checked_count,
        "first_invalid_event_id": first_invalid_event_id,
        "failure_reason": failure_reason,
    }


def verify_audit_chain(db: Session, tenant_id: str) -> dict:
    """Verify the complete persisted chain for one authorized tenant.

    Events are ordered by the same created_at/id convention used by the
    append writer. An empty tenant chain is valid with zero checked events.
    """
    entries = db.scalars(
        select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    ).all()
    expected_previous_hash = None
    for index, entry in enumerate(entries):
        checked_count = index + 1
        event_id = entry.id if isinstance(entry.id, str) else None
        if not entry.created_at or any(
            not isinstance(value, str) or not value
            for value in (entry.tenant_id, entry.actor_id, entry.action, entry.entity_type, entry.entity_id)
        ):
            return _verification_result(
                valid=False, checked_count=checked_count,
                first_invalid_event_id=event_id, failure_reason="malformed_event",
            )
        if index == 0:
            if entry.previous_hash is not None:
                return _verification_result(
                    valid=False, checked_count=checked_count,
                    first_invalid_event_id=event_id, failure_reason="invalid_genesis",
                )
        elif entry.previous_hash != expected_previous_hash:
            return _verification_result(
                valid=False, checked_count=checked_count,
                first_invalid_event_id=event_id, failure_reason="previous_hash_mismatch",
            )
        if entry.previous_hash is not None and (
            not isinstance(entry.previous_hash, str)
            or len(entry.previous_hash) != 64
            or any(character not in "0123456789abcdef" for character in entry.previous_hash.lower())
        ):
            return _verification_result(
                valid=False, checked_count=checked_count,
                first_invalid_event_id=event_id, failure_reason="malformed_event",
            )
        try:
            payload = json.loads(entry.payload_json)
        except (TypeError, json.JSONDecodeError):
            return _verification_result(
                valid=False, checked_count=checked_count,
                first_invalid_event_id=event_id, failure_reason="malformed_event",
            )
        if not isinstance(payload, dict) or not isinstance(entry.entry_hash, str):
            return _verification_result(
                valid=False, checked_count=checked_count,
                first_invalid_event_id=event_id, failure_reason="malformed_event",
            )
        if len(entry.entry_hash) != 64 or any(
            character not in "0123456789abcdef" for character in entry.entry_hash.lower()
        ):
            return _verification_result(
                valid=False, checked_count=checked_count,
                first_invalid_event_id=event_id, failure_reason="malformed_event",
            )
        expected_hash = calculate_audit_hash(
            tenant_id=entry.tenant_id, actor_id=entry.actor_id, action=entry.action,
            entity_type=entry.entity_type, entity_id=entry.entity_id,
            payload=payload, previous_hash=entry.previous_hash,
        )
        if entry.entry_hash != expected_hash:
            return _verification_result(
                valid=False, checked_count=checked_count,
                first_invalid_event_id=event_id, failure_reason="event_hash_mismatch",
            )
        expected_previous_hash = entry.entry_hash
    return _verification_result(valid=True, checked_count=len(entries))

def append_audit(
    db: Session, *, tenant_id: str, actor_id: str, action: str,
    entity_type: str, entity_id: str, payload: dict
) -> AuditLog:
    # Application-level append-only pattern. A privileged DB administrator can still
    # alter rows unless DB permissions/triggers and external/WORM checkpoints are added.
    previous = db.scalar(
        select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)
    )
    previous_hash = previous.entry_hash if previous else None
    entry_hash = calculate_audit_hash(
        tenant_id=tenant_id, actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        payload=payload, previous_hash=previous_hash,
    )
    entry = AuditLog(
        tenant_id=tenant_id, actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        previous_hash=previous_hash, entry_hash=entry_hash
    )
    db.add(entry)
    db.flush()
    return entry
