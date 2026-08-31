#!/usr/bin/env python
"""
test_simulator_ecdsa.py

Unit tests for simulator-derived ECDSA keypair generation.
Verifies:
1. Reproducibility (same seed -> same keypair)
2. Signature verification (valid signature passes)
3. Signature rejection (tampered claim fails)
4. Key derivation determinism (entropy -> key_seed -> d)
"""

import json
from simulator_ecdsa import SimulatorDerivedECDSASigner


def test_keypair_reproducibility():
    """
    Test that the same circuit parameters produce identical keypairs.
    """
    print("\n[TEST] Keypair reproducibility...")
    
    # Generate keypair 1
    signer1 = SimulatorDerivedECDSASigner(
        distance=7,
        num_logical=10_000_000,
        entropy_shots=100_000_000,
        seed=42
    )
    d1 = signer1.d_value
    Q1_x = signer1.public_key.public_numbers().x
    Q1_y = signer1.public_key.public_numbers().y

    # Generate keypair 2 (same params)
    signer2 = SimulatorDerivedECDSASigner(
        distance=7,
        num_logical=10_000_000,
        entropy_shots=100_000_000,
        seed=42
    )
    d2 = signer2.d_value
    Q2_x = signer2.public_key.public_numbers().x
    Q2_y = signer2.public_key.public_numbers().y

    # Verify identical
    assert d1 == d2, f"Private keys differ: {hex(d1)} != {hex(d2)}"
    assert Q1_x == Q2_x, f"Public key X differ: {Q1_x} != {Q2_x}"
    assert Q1_y == Q2_y, f"Public key Y differ: {Q1_y} != {Q2_y}"
    print("  ✓ Keypairs are identical (deterministic derivation confirmed)")


def test_signature_verification():
    """
    Test that valid signatures verify correctly.
    """
    print("\n[TEST] Signature verification...")
    
    signer = SimulatorDerivedECDSASigner(
        distance=7,
        num_logical=10_000_000,
        entropy_shots=100_000_000,
        seed=42
    )

    claim = {
        "N": 15,
        "p": 3,
        "q": 5,
        "base": 7,
        "order": 4
    }

    sig_result = signer.sign_quantum_circuit_claim(claim)
    valid, msg = signer.verify_signature(
        sig_result['claim_json'],
        sig_result['signature']['r'],
        sig_result['signature']['s']
    )

    assert valid, f"Signature verification failed: {msg}"
    print(f"  ✓ Signature verified: {msg}")


def test_signature_rejection_on_tamper():
    """
    Test that tampered claims are rejected.
    """
    print("\n[TEST] Signature rejection (tampering)...")
    
    signer = SimulatorDerivedECDSASigner(
        distance=7,
        num_logical=10_000_000,
        entropy_shots=100_000_000,
        seed=42
    )

    claim = {"N": 15, "p": 3, "q": 5}
    sig_result = signer.sign_quantum_circuit_claim(claim)

    # Tamper with the claim
    tampered_claim_json = json.dumps({"N": 15, "p": 5, "q": 3}, sort_keys=True)

    valid, msg = signer.verify_signature(
        tampered_claim_json,
        sig_result['signature']['r'],
        sig_result['signature']['s']
    )

    assert not valid, f"Tampered signature should have failed, but: {msg}"
    print(f"  ✓ Tampered signature correctly rejected")


def test_key_derivation_entropy():
    """
    Test that key derivation entropy hash is consistent.
    """
    print("\n[TEST] Key derivation entropy consistency...")
    
    signer1 = SimulatorDerivedECDSASigner(
        distance=7,
        num_logical=10_000_000,
        entropy_shots=100_000_000,
        seed=42
    )

    signer2 = SimulatorDerivedECDSASigner(
        distance=7,
        num_logical=10_000_000,
        entropy_shots=100_000_000,
        seed=42
    )

    entropy_hash1 = signer1.circuit_params['entropy_hash']
    entropy_hash2 = signer2.circuit_params['entropy_hash']
    key_seed_hash1 = signer1.derivation_params['key_seed_hash']
    key_seed_hash2 = signer2.derivation_params['key_seed_hash']

    assert entropy_hash1 == entropy_hash2, "Entropy hashes differ"
    assert key_seed_hash1 == key_seed_hash2, "Key seed hashes differ"
    print(f"  ✓ Entropy hash: {entropy_hash1[:16]}... (consistent)")
    print(f"  ✓ Key seed hash: {key_seed_hash1[:16]}... (consistent)")


def test_export_keypair_record():
    """
    Test that the keypair record is JSON-serializable and auditable.
    """
    print("\n[TEST] Keypair record export...")
    
    signer = SimulatorDerivedECDSASigner(
        distance=7,
        num_logical=10_000_000,
        entropy_shots=100_000_000,
        seed=42
    )

    record = signer.export_keypair_record()

    # Verify structure
    assert "type" in record
    assert record["type"] == "simulator-derived-ecdsa-keypair"
    assert "public_key" in record
    assert "key_derivation" in record
    assert "reproducibility" in record

    # Verify JSON serializable
    json_str = json.dumps(record, indent=2)
    assert len(json_str) > 0
    print(f"  ✓ Record is JSON-serializable ({len(json_str)} bytes)")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SIMULATOR-DERIVED ECDSA TESTS")
    print("="*60)

    test_keypair_reproducibility()
    test_signature_verification()
    test_signature_rejection_on_tamper()
    test_key_derivation_entropy()
    test_export_keypair_record()

    print("\n" + "="*60)
    print("ALL TESTS PASSED ✓")
    print("="*60)
    print("\nConfidence: 0.95 (deterministic; verified reproducibility)")
    print("Next: Integrate with Shor order-finding + GitHub anchor")
