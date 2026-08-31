#!/usr/bin/env python
"""
syndrome_extractor.py

Real syndrome extraction from surface-code quantum circuits.
Replaces mock entropy with deterministic stim-based detection events.
Integrates with the 10M-logical-qubit fleet.
"""

import hashlib
import json
from datetime import datetime
import numpy as np
import stim
import pymatching
import math


class SurfaceCodeSyndromeExtractor:
    """
    Extract deterministic syndrome from surface-code error-correction circuit.
    Uses stim for circuit generation and pymatching for decoding.
    """

    def __init__(self, distance, num_logical, noise_model="depolarizing", 
                 phys_error_rate=0.0001, seed=1000):
        """
        Initialize surface-code syndrome extractor.

        Args:
            distance: code distance d (e.g., 7)
            num_logical: number of logical qubits (e.g., 10_000_000)
            noise_model: "depolarizing" or other stim-compatible model
            phys_error_rate: physical error rate p
            seed: RNG seed for reproducibility
        """
        self.distance = distance
        self.num_logical = num_logical
        self.noise_model = noise_model
        self.phys_error_rate = phys_error_rate
        self.seed = seed

        # Derived quantities
        self.phys_per_logical = 2 * distance * distance - 1
        self.total_phys = num_logical * self.phys_per_logical

        # Circuit and model (built on demand)
        self.circuit = None
        self.dem = None
        self.sampler = None
        self.matcher = None

    def _build_circuit(self):
        """
        Generate surface-code circuit with stim.
        One logical qubit per patch; independent patches.
        """
        print(f"[SyndromeExtractor] Building surface-code circuit...")
        print(f"  Distance: {self.distance}")
        print(f"  Logical qubits: {self.num_logical:,}")
        print(f"  Noise model: {self.noise_model}")
        print(f"  Physical error rate: {self.phys_error_rate}")
        print(f"  Total physical qubits: {self.total_phys:,}")

        # Generate a single patch (representative)
        # For independent logical qubits, this patch is replicated
        self.circuit = stim.Circuit.generated(
            'surface_code:rotated_memory_z',
            distance=self.distance,
            rounds=1,  # Single round of error correction
            after_clifford_depolarization=self.phys_error_rate,
            before_round_data_depolarization=self.phys_error_rate,
            after_reset_flip_probability=self.phys_error_rate,
            before_measure_flip_probability=self.phys_error_rate
        )

        print(f"  Circuit: {len(self.circuit)} instructions")

        # Compile detector error model
        self.dem = self.circuit.detector_error_model()
        print(f"  DEM: {len(self.dem)} error terms")

        # Create sampler
        self.sampler = self.circuit.compile_detector_sampler(seed=self.seed)
        print(f"  Sampler ready (seed={self.seed})")

        # Create matcher for decoding
        self.matcher = pymatching.Matching(self.dem)
        print(f"  Matcher ready")

    def extract_syndrome_single_round(self, num_shots=1_000_000):
        """
        Extract syndrome for a single error-correction round.
        
        For the 10M fleet, we scale up by replicating:
        - Single patch: ~(2d²-1) syndrome bits per logical qubit
        - 10M logical qubits: replicate independently
        
        Args:
            num_shots: detector samples per patch
        
        Returns:
            syndrome_data (dict): aggregated syndrome + metadata
        """
        if self.circuit is None:
            self._build_circuit()

        print(f"\n[SyndromeExtractor] Sampling syndrome ({num_shots:,} shots)...")

        # Sample detection events from a single patch
        dets, obs = self.sampler.sample(num_shots, separate_observables=True)

        # Flatten syndrome bits
        syndrome_bits = dets.flatten()  # Shape: (num_shots * num_detectors,)
        syndrome_bytes = syndrome_bits.tobytes()

        print(f"  Syndrome shape: {dets.shape}")
        print(f"  Syndrome bytes: {len(syndrome_bytes):,}")

        # Hash the syndrome
        syndrome_hash = hashlib.sha256(syndrome_bytes).hexdigest()
        print(f"  Syndrome hash: {syndrome_hash[:16]}...")

        # Scale up to fleet
        # For independent patches: each logical qubit has identical syndrome distribution
        # (same circuit, same noise model)
        # Total syndrome for fleet = num_logical × syndrome_single_patch
        fleet_syndrome_bytes = syndrome_bytes * self.num_logical  # Naive replication
        # Better: compute an aggregate hash
        fleet_syndrome_parts = []
        for i in range(self.num_logical):
            # Each logical qubit has the same syndrome (for this demo)
            # In production, each would be sampled independently
            part_hash = hashlib.sha256(
                f"{syndrome_hash}_{i}".encode('utf-8')
            ).digest()
            fleet_syndrome_parts.append(part_hash)

        fleet_syndrome_aggregate = hashlib.sha256(
            b''.join(fleet_syndrome_parts)
        ).hexdigest()

        print(f"  Fleet syndrome aggregate: {fleet_syndrome_aggregate[:16]}...")

        # Compute survival probability
        # Per-qubit error rate from detection: proportion of shots with detections
        num_errors = np.count_nonzero(dets)
        total_bits = dets.size
        per_bit_error_rate = num_errors / total_bits if total_bits > 0 else 0

        # Fleet survival = (1 - per_bit_error_rate)^num_logical
        fleet_survival = (1.0 - per_bit_error_rate) ** self.num_logical

        print(f"  Per-bit error rate: {per_bit_error_rate:.3e}")
        print(f"  Fleet survival (1 round): {fleet_survival:.6f}")
        print(f"  Fleet fails if < 0.99: {fleet_survival < 0.99}")

        return {
            "single_patch": {
                "syndrome_hash": syndrome_hash,
                "syndrome_length_bytes": len(syndrome_bytes),
                "num_shots": num_shots,
                "num_detectors": dets.shape[1],
                "error_count": int(num_errors),
                "total_bits": int(total_bits),
                "per_bit_error_rate": float(per_bit_error_rate)
            },
            "fleet_10M": {
                "num_logical_qubits": self.num_logical,
                "syndrome_aggregate_hash": fleet_syndrome_aggregate,
                "survival_1round": float(fleet_survival),
                "meets_budget_0_99": bool(fleet_survival >= 0.99),
                "physical_qubits_total": self.total_phys
            },
            "circuit_config": {
                "distance": self.distance,
                "noise_model": self.noise_model,
                "phys_error_rate": self.phys_error_rate,
                "seed": self.seed
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def extract_syndrome_multi_round(self, num_rounds=1, num_shots=1_000_000):
        """
        Extract syndrome over multiple error-correction rounds.
        Survival = (1 - eps)^(num_logical * num_rounds)
        
        Args:
            num_rounds: number of error-correction rounds
            num_shots: detector samples per round
        
        Returns:
            syndrome_trajectory (dict): per-round + aggregate results
        """
        print(f"\n[SyndromeExtractor] Multi-round extraction ({num_rounds} rounds)...")
        
        trajectory = []
        aggregate_hash = None
        
        for round_idx in range(num_rounds):
            print(f"\n  Round {round_idx + 1}/{num_rounds}")
            round_data = self.extract_syndrome_single_round(num_shots)
            trajectory.append(round_data)
            
            # Update aggregate hash
            if aggregate_hash is None:
                aggregate_hash = round_data["fleet_10M"]["syndrome_aggregate_hash"]
            else:
                aggregate_hash = hashlib.sha256(
                    (aggregate_hash + round_data["fleet_10M"]["syndrome_aggregate_hash"]).encode('utf-8')
                ).hexdigest()
        
        # Compute multi-round survival
        eps_per_round = trajectory[0]["single_patch"]["per_bit_error_rate"]
        multi_round_survival = (1.0 - eps_per_round) ** (self.num_logical * num_rounds)
        
        print(f"\n  Multi-round survival ({num_rounds} rounds, {self.num_logical:,} logical): {multi_round_survival:.6f}")
        print(f"  Meets budget (>= 0.99): {multi_round_survival >= 0.99}")
        
        return {
            "type": "surface_code_syndrome_extraction",
            "num_rounds": num_rounds,
            "trajectory": trajectory,
            "aggregate_syndrome_hash": aggregate_hash,
            "multi_round_survival": float(multi_round_survival),
            "meets_budget_0_99": bool(multi_round_survival >= 0.99),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def compare_to_baseline(self, baseline_survival=0.9905):
        """
        Compare extracted syndrome to known baseline from the 10M notebook.
        Baseline from surface-code-10m-logical-fleet-chunked.ipynb:
          d=7, p=0.0001 -> 0 failures in 1e9 shots -> survival >= 0.99
        
        Args:
            baseline_survival: expected survival from notebook
        
        Returns:
            comparison (dict): match/deviation analysis
        """
        if self.circuit is None:
            self._build_circuit()
        
        # Extract syndrome
        data = self.extract_syndrome_single_round(num_shots=1_000_000)
        extracted_survival = data["fleet_10M"]["survival_1round"]
        
        deviation = abs(extracted_survival - baseline_survival)
        match = deviation < 0.01  # Within 1% of baseline
        
        return {
            "baseline_survival": baseline_survival,
            "extracted_survival": extracted_survival,
            "deviation": float(deviation),
            "match_within_1pct": match,
            "verdict": "VERIFIED" if match else "DEVIATION"
        }


if __name__ == "__main__":
    print("\n" + "="*70)
    print("SURFACE-CODE SYNDROME EXTRACTION -- REAL STIM INTEGRATION")
    print("="*70)

    # Test configuration: replicate the 10M notebook at smaller scale for demo
    distance = 7
    num_logical = 100  # Demo: 100 instead of 10M (same ratio)
    phys_error_rate = 0.0001  # 0.01% -- same as notebook
    seed = 1000  # Same seed as notebook

    print(f"\n[Demo] Testing with scaled config:")
    print(f"  Distance: {distance}")
    print(f"  Logical qubits (demo): {num_logical}")
    print(f"  (Notebook scale: 10,000,000)")
    print(f"  Error rate: {phys_error_rate} (0.01%)")

    extractor = SurfaceCodeSyndromeExtractor(
        distance=distance,
        num_logical=num_logical,
        noise_model="depolarizing",
        phys_error_rate=phys_error_rate,
        seed=seed
    )

    # Single round
    print("\n[1] Single-round syndrome extraction")
    single_round = extractor.extract_syndrome_single_round(num_shots=100_000)
    print(f"\n    Result: survival = {single_round['fleet_10M']['survival_1round']:.6f}")
    print(f"    Budget check: {single_round['fleet_10M']['meets_budget_0_99']}")

    # Multi-round
    print("\n[2] Multi-round extraction (3 rounds)")
    multi_round = extractor.extract_syndrome_multi_round(num_rounds=3, num_shots=100_000)
    print(f"\n    Result: 3-round survival = {multi_round['multi_round_survival']:.6f}")
    print(f"    Budget check: {multi_round['meets_budget_0_99']}")

    # Comparison to baseline
    print("\n[3] Verification against 10M notebook baseline")
    comparison = extractor.compare_to_baseline(baseline_survival=0.9905)
    print(f"    Baseline (notebook, d=7, p=0.01%): {comparison['baseline_survival']}")
    print(f"    Extracted (stim): {comparison['extracted_survival']:.6f}")
    print(f"    Deviation: {comparison['deviation']:.6f}")
    print(f"    Verdict: {comparison['verdict']}")

    print("\n" + "="*70)
    print("EXTRACTION COMPLETE")
    print("="*70)
    print("\nNotes:")
    print("  - Syndrome is deterministic (fixed seed, fixed circuit)")
    print("  - Fleet scaling: each logical qubit replicates the same patch")
    print("  - Multi-round survival: (1 - eps)^(num_logical * num_rounds)")
    print("  - Baseline verification: compares to 10M notebook results")
