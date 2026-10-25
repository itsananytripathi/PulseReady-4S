from app.merkle import (
    MerkleCheckpoint,
    build_proof,
    leaf_hash,
    merkle_root,
    verify_proof,
)
from types import SimpleNamespace
from app.merkle import checkpoint_from_audit_entries, verify_audit_inclusion


def leaves(count):
    return [leaf_hash(f"event-{index}") for index in range(count)]


def test_single_and_empty_tree_conventions():
    one = leaves(1)
    assert merkle_root([]) is None
    assert merkle_root(one) == one[0]
    assert verify_proof(build_proof(one, 0), one[0])


def test_inclusion_proofs_first_middle_and_final_for_odd_tree():
    values = leaves(5)
    root = merkle_root(values)
    assert root is not None
    for index in (0, 2, 4):
        assert verify_proof(build_proof(values, index), root)


def test_tampered_proof_metadata_and_sibling_fail_closed():
    values = leaves(5)
    proof = build_proof(values, 2)
    root = merkle_root(values)
    assert not verify_proof(proof.__class__(3, proof.tree_size, proof.leaf_hash, proof.steps), root)
    tampered = proof.__class__(proof.leaf_index, proof.tree_size, proof.leaf_hash, proof.steps[:-1])
    assert not verify_proof(tampered, root)
    assert not verify_proof(proof, "0" * 64)


def test_checkpoint_is_explicitly_versioned_and_does_not_claim_immutability():
    checkpoint = MerkleCheckpoint("checkpoint-1", 0, None, tuple())
    assert checkpoint.format_version == "merkle-v1"
    assert checkpoint.root_hash is None


def test_audit_checkpoint_binds_proof_to_trusted_event_content():
    entries = [SimpleNamespace(
        id=f"event-{index}", created_at=index, tenant_id="tenant-a", actor_id="actor",
        action="test", entity_type="test", entity_id=f"entity-{index}",
        payload_json='{"index": %d}' % index, previous_hash=None,
    ) for index in range(3)]
    checkpoint, hashes = checkpoint_from_audit_entries("checkpoint-a", entries)
    proof = build_proof(hashes, 1)
    assert verify_audit_inclusion(entries[1], proof, checkpoint)
    altered = SimpleNamespace(**{**entries[1].__dict__, "payload_json": '{"index": 99}'})
    assert not verify_audit_inclusion(altered, proof, checkpoint)
