"""
Quantum Bridge Transpiler
===========================
Translates IBM Qiskit quantum circuits into hardware-native IR,
enabling Qiskit users to run circuits on alternative quantum backends.

Supported gates:
  Single-qubit: H, X, Y, Z, S, T, Rx, Ry, Rz, U1, U2, U3, I
  Two-qubit: CNOT/CX, CZ, SWAP, CR (controlled rotation)
  Three-qubit: Toffoli (CCX), CSWAP (Fredkin)
  Measurement: measure → MEASURE
  Barrier: barrier → BARRIER

Usage:
  from qiskit_to_originir import transpile
  ir_code = transpile(qiskit_circuit)
"""

import math
from typing import Optional

# Qiskit gate name → OriginIR gate mapping
# Format: qiskit_name → (originir_name, param_count)
GATE_MAP = {
    # Single-qubit, no params
    "h":     ("H", 0),
    "x":     ("X", 0),
    "y":     ("Y", 0),
    "z":     ("Z", 0),
    "s":     ("S", 0),
    "t":     ("T", 0),
    "sdg":   ("S", 0, True),   # S-dagger → DAGGER S
    "tdg":   ("T", 0, True),   # T-dagger → DAGGER T
    "id":    ("I", 0),
    "i":     ("I", 0),

    # Single-qubit, parameterized
    "rx":    ("RX", 1),
    "ry":    ("RY", 1),
    "rz":    ("RZ", 1),
    "p":     ("RZ", 1),        # Phase gate ≡ RZ (global phase differs, irrelevant for measurement)
    "u1":    ("RZ", 1),        # U1 ≡ RZ up to global phase
    "u2":    ("U2", 2),
    "u3":    ("U3", 3),
    "u":     ("U3", 3),

    # Two-qubit
    "cx":    ("CNOT", 0),
    "cnot":  ("CNOT", 0),
    "cz":    ("CZ", 0),
    "swap":  ("SWAP", 0),
    "cp":    ("CR", 1),        # Controlled-phase → CR
    "crz":   ("CR", 1),

    # Three-qubit
    "ccx":   ("TOFFOLI", 0),
    "cswap": ("CSWAP", 0),
}


def _format_params(params: list) -> str:
    """Format gate parameters as OriginIR angle strings."""
    formatted = []
    for p in params:
        # Try to express as pi fraction for readability
        val = float(p)
        ratio = val / math.pi
        if abs(ratio - round(ratio, 6)) < 1e-9:
            r = round(ratio, 6)
            if r == 1.0:
                formatted.append("pi")
            elif r == -1.0:
                formatted.append("-pi")
            elif r == 0.0:
                formatted.append("0")
            else:
                formatted.append(f"{r}*pi")
        else:
            formatted.append(f"{val:.10g}")
    return ", ".join(formatted)


def _qubit_ref(bit, qubit_indices: dict) -> str:
    """Convert a Qiskit qubit to OriginIR q[n] reference."""
    idx = qubit_indices.get(bit)
    if idx is None:
        raise ValueError(f"Unknown qubit: {bit}")
    return f"q[{idx}]"


def _cbit_ref(bit, clbit_indices: dict) -> str:
    """Convert a Qiskit classical bit to OriginIR c[n] reference."""
    idx = clbit_indices.get(bit)
    if idx is None:
        raise ValueError(f"Unknown classical bit: {bit}")
    return f"c[{idx}]"


def transpile(circuit, *, include_header: bool = True) -> str:
    """
    Transpile a Qiskit QuantumCircuit to OriginIR string.

    Args:
        circuit: A qiskit.circuit.QuantumCircuit object
        include_header: Include QINIT/CREG header lines

    Returns:
        OriginIR program as a string
    """
    lines = []

    # Build qubit/clbit index maps
    qubit_indices = {bit: i for i, bit in enumerate(circuit.qubits)}
    clbit_indices = {bit: i for i, bit in enumerate(circuit.clbits)}

    n_qubits = len(circuit.qubits)
    n_clbits = len(circuit.clbits)

    if include_header:
        lines.append(f"QINIT {n_qubits}")
        lines.append(f"CREG {n_clbits}")

    for instruction in circuit.data:
        # Handle both Qiskit 0.x and 1.x instruction formats
        if hasattr(instruction, 'operation'):
            # Qiskit 1.x: CircuitInstruction
            op = instruction.operation
            qargs = instruction.qubits
            cargs = instruction.clbits
        else:
            # Qiskit 0.x: tuple (gate, qubits, clbits)
            op, qargs, cargs = instruction

        gate_name = op.name.lower()
        params = op.params

        # --- Measurement ---
        if gate_name == "measure":
            q = _qubit_ref(qargs[0], qubit_indices)
            c = _cbit_ref(cargs[0], clbit_indices)
            lines.append(f"MEASURE {q}, {c}")
            continue

        # --- Barrier ---
        if gate_name == "barrier":
            qrefs = ", ".join(_qubit_ref(q, qubit_indices) for q in qargs)
            lines.append(f"BARRIER {qrefs}")
            continue

        # --- Reset ---
        if gate_name == "reset":
            q = _qubit_ref(qargs[0], qubit_indices)
            lines.append(f"MEASURE {q}, c[0]")
            lines.append(f"# RESET {q} (measure + conditional X)")
            continue

        # --- Gate lookup ---
        mapping = GATE_MAP.get(gate_name)
        if mapping is None:
            # Try to decompose unknown gates
            lines.append(f"# UNSUPPORTED: {gate_name} — decompose first")
            continue

        is_dagger = len(mapping) == 3 and mapping[2] is True
        origin_name = mapping[0]
        expected_params = mapping[1]

        # Build qubit references
        qrefs = ", ".join(_qubit_ref(q, qubit_indices) for q in qargs)

        # Build the instruction line
        if is_dagger:
            lines.append(f"DAGGER")
            if expected_params > 0 and params:
                lines.append(f"{origin_name} {qrefs}, ({_format_params(params)})")
            else:
                lines.append(f"{origin_name} {qrefs}")
            lines.append(f"ENDDAGGER")
        else:
            if expected_params > 0 and params:
                lines.append(f"{origin_name} {qrefs}, ({_format_params(params)})")
            else:
                lines.append(f"{origin_name} {qrefs}")

    return "\n".join(lines)


def transpile_file(qasm_str: str) -> str:
    """
    Transpile an OpenQASM 2.0 string to OriginIR.
    Requires qiskit to parse the QASM.
    """
    from qiskit import QuantumCircuit
    circuit = QuantumCircuit.from_qasm_str(qasm_str)
    return transpile(circuit)


# --- Reverse direction: OriginIR → Qiskit (for completeness) ---

REVERSE_GATE_MAP = {
    "H": "h", "X": "x", "Y": "y", "Z": "z",
    "S": "s", "T": "t", "I": "id",
    "RX": "rx", "RY": "ry", "RZ": "rz",
    "CNOT": "cx", "CZ": "cz", "SWAP": "swap",
    "TOFFOLI": "ccx", "CSWAP": "cswap",
    "CR": "crz",
}


if __name__ == "__main__":
    # Demo: create a simple Qiskit circuit and transpile it
    try:
        from qiskit import QuantumCircuit

        qc = QuantumCircuit(3, 3)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc.rx(math.pi / 4, 0)
        qc.barrier()
        qc.measure([0, 1, 2], [0, 1, 2])

        print("=== Qiskit Circuit ===")
        print(qc)
        print()
        print("=== OriginIR Output ===")
        print(transpile(qc))
    except ImportError:
        print("Qiskit not installed. Install with: pip install qiskit")
        print()
        print("Showing gate map instead:")
        for q, o in sorted(GATE_MAP.items()):
            print(f"  {q:8s} → {o[0]}")
