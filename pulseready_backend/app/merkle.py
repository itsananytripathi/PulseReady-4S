"""Small domain-separated binary Merkle primitives for optional checkpoints.

Convention: leaves are ordered by the caller, odd levels duplicate the final
node, and an empty tree has root ``None``. This module does not persist or
trust client-supplied event content; callers must obtain events from their
trusted database before constructing a checkpoint.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Sequence

from app.audit import canonical_audit_json


LEAF_DOMAIN = b"PulseReady4S-MerkleLeaf\x00"
NODE_DOMAIN = b"PulseReady4S-MerkleNode\x00"
FORMAT_VERSION = "merkle-v1"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leaf_hash(canonical_event: str | bytes) -> str:
    value = canonical_event.encode("utf-8") if isinstance(canonical_event, str) else canonical_event
    return _digest(LEAF_DOMAIN + value)


def node_hash(left: str, right: str) -> str:
    try:
        left_bytes = bytes.fromhex(left)
        right_bytes = bytes.fromhex(right)
    except ValueError as exc:
        raise ValueError("Merkle node hashes must be hexadecimal SHA-256 values") from exc
    if len(left_bytes) != 32 or len(right_bytes) != 32:
        raise ValueError("Merkle node hashes must be 32 bytes")
    return _digest(NODE_DOMAIN + left_bytes + right_bytes)


@dataclass(frozen=True)
class MerkleProofStep:
    sibling_hash: str
    sibling_is_left: bool


@dataclass(frozen=True)
class MerkleProof:
    leaf_index: int
    tree_size: int
    leaf_hash: str
    steps: tuple[MerkleProofStep, ...]


@dataclass(frozen=True)
class MerkleCheckpoint:
    checkpoint_id: str
    tree_size: int
    root_hash: str | None
    covered_event_ids: tuple[str, ...]
    algorithm: str = "sha256"
    format_version: str = FORMAT_VERSION


def _validate_hash(value: str) -> None:
    try:
        raw = bytes.fromhex(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_hash_encoding") from exc
    if len(raw) != 32:
        raise ValueError("invalid_hash_encoding")


def merkle_root(leaves: Sequence[str]) -> str | None:
    if not leaves:
        return None
    for value in leaves:
        _validate_hash(value)
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def build_proof(leaves: Sequence[str], leaf_index: int) -> MerkleProof:
    if not 0 <= leaf_index < len(leaves):
        raise ValueError("leaf_index_out_of_range")
    for value in leaves:
        _validate_hash(value)
    index = leaf_index
    level = list(leaves)
    steps: list[MerkleProofStep] = []
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sibling_index = index - 1 if index % 2 else index + 1
        steps.append(MerkleProofStep(level[sibling_index], sibling_index < index))
        level = [node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        index //= 2
    return MerkleProof(leaf_index, len(leaves), leaves[leaf_index], tuple(steps))


def verify_proof(proof: MerkleProof, expected_root: str | None) -> bool:
    if proof.tree_size <= 0 or not 0 <= proof.leaf_index < proof.tree_size:
        return False
    if expected_root is None:
        return False
    try:
        _validate_hash(proof.leaf_hash)
        _validate_hash(expected_root)
        current = proof.leaf_hash
        level_size = proof.tree_size
        index = proof.leaf_index
        for step in proof.steps:
            if level_size <= 1:
                return False
            expected_sibling_is_left = index % 2 == 1
            # An odd final node is duplicated, so its sibling is itself.
            if level_size % 2 and index == level_size - 1:
                expected_sibling_is_left = False
            if step.sibling_is_left != expected_sibling_is_left:
                return False
            _validate_hash(step.sibling_hash)
            current = node_hash(step.sibling_hash, current) if step.sibling_is_left else node_hash(current, step.sibling_hash)
            index //= 2
            level_size = (level_size + 1) // 2
        if level_size != 1 or index != 0:
            return False
        return current == expected_root
    except ValueError:
        return False


def checkpoint_from_audit_entries(checkpoint_id: str, entries: Sequence[object]) -> tuple[MerkleCheckpoint, tuple[str, ...]]:
    """Create an in-memory checkpoint from already committed audit ORM rows."""
    ordered = sorted(entries, key=lambda entry: (entry.created_at, entry.id))
    event_ids = tuple(entry.id for entry in ordered)
    leaves = []
    for entry in ordered:
        payload = json.loads(entry.payload_json)
        canonical = canonical_audit_json(
            tenant_id=entry.tenant_id, actor_id=entry.actor_id, action=entry.action,
            entity_type=entry.entity_type, entity_id=entry.entity_id,
            payload=payload, previous_hash=entry.previous_hash,
        )
        leaves.append(leaf_hash(canonical))
    return MerkleCheckpoint(checkpoint_id, len(leaves), merkle_root(leaves), event_ids), tuple(leaves)


def verify_audit_inclusion(entry: object, proof: MerkleProof, checkpoint: MerkleCheckpoint) -> bool:
    """Bind a proof to the trusted persisted event, not client-supplied content."""
    if proof.tree_size != checkpoint.tree_size or proof.leaf_index >= len(checkpoint.covered_event_ids):
        return False
    if checkpoint.covered_event_ids[proof.leaf_index] != entry.id:
        return False
    try:
        payload = json.loads(entry.payload_json)
        canonical = canonical_audit_json(
            tenant_id=entry.tenant_id, actor_id=entry.actor_id, action=entry.action,
            entity_type=entry.entity_type, entity_id=entry.entity_id,
            payload=payload, previous_hash=entry.previous_hash,
        )
        return leaf_hash(canonical) == proof.leaf_hash and verify_proof(proof, checkpoint.root_hash)
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return False
