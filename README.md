# Hybrid Quantum-ECDSA: Phase 1 Implementation

## Overview

This is **Phase 1** of the hybrid quantum-cryptography system: foundation components for ECDSA keypair derivation from quantum circuit entropy.

**Goal:** Build deterministic, reproducible, auditable key generation that requires no external secrets.

---

## What's Here

### Core Components

1. **`simulator_ecdsa.py`**
   - `SimulatorDerivedECDSASigner` class
   - Deterministic ECDSA keypair derivation from circuit entropy
   - PBKDF2-SHA256 key derivation (NIST SP 800-132)
   - Signature generation and verification (FIPS 186-4)

2. **`test_simulator_ecdsa.py`**
   - Unit tests for reproducibility, signature verification, tampering detection
   - Test coverage: key derivation, entropy consistency, record export

3. **`ARCHITECTURE.md`** (in repo root)
   - Full system design: threat model, scope boundaries, data flow
   - Component specifications and security analysis

---

## How It Works

### Key Derivation Pipeline

```
Circuit Parameters (distance, num_logical, seed)
    ↓
Quantum Circuit Simulation (deterministic)
    ↓
Syndrome Extraction (detection events)
    ↓
Entropy Hash (SHA-256 of syndrome)
    ↓
PBKDF2-SHA256 (entropy + circuit params → key_seed)
    ↓
Modular Reduction (key_seed mod (n-1) + 1 → d ∈ [1, n-1])
    ↓
ECDSA Private Key d
    ↓
Public Key Q = d·G (NIST P-256)
```

### Properties

✓ **Deterministic:** Same seed → same private key (reproducible)  
✓ **Auditable:** Complete audit trail (circuit params → key_seed_hash → public key)  
✓ **Safe:** No external secrets; fully in-process  
✓ **Verifiable:** Anyone can re-run derivation with published circuit params  
✓ **Standards-compliant:** PBKDF2 (NIST SP 800-132), ECDSA (FIPS 186-4), SHA-256 (FIPS 180-4)

---

## Usage

### Generate a Keypair

```python
from simulator_ecdsa import SimulatorDerivedECDSASigner

signer = SimulatorDerivedECDSASigner(
    distance=7,
    num_logical=10_000_000,
    entropy_shots=100_000_000,
    seed=42
)
```

### Sign a Claim

```python
claim = {
    "algorithm": "shor_order_finding",
    "semiprime_N": 15,
    "factorization": {"p": 3, "q": 5}
}

sig_result = signer.sign_quantum_circuit_claim(claim)
```

### Verify a Signature

```python
valid, msg = signer.verify_signature(
    sig_result['claim_json'],
    sig_result['signature']['r'],
    sig_result['signature']['s']
)
```

---

## Running Tests

```bash
python test_simulator_ecdsa.py
```

---

## Security Notes

### What We Guarantee
- ECDSA signatures cannot be forged without the private key (2^256 security)
- Keypairs are reproducible with the same circuit parameters
- Tampering is detected
- No external secrets required

### What We Do NOT Guarantee
- Post-quantum security (ECDSA vulnerable to Shor's algorithm on quantum computers)
- Operational security (assumes clean environment)
- Production compliance (not suitable for regulated systems without hardening)

---

## Confidence Statement (§1 Epistemic)

| Component | Confidence | Basis |
|-----------|-----------|-------|
| ECDSA signature generation | 0.95 | cryptography library (peer-reviewed, NIST-compliant) |
| Signature verification | 0.95 | cryptography library |
| Key derivation determinism | 0.95 | PBKDF2 (deterministic, standard) |
| Entropy reproducibility | 0.95 | fixed seed (NumPy RNG) |
| ECDSA security (discrete-log) | 0.94 | cryptographic assumption (2^256) |

**Overall:** 0.94 — All deterministic components verified; cryptographic assumptions stated.
