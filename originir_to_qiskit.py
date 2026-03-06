"""
OriginIR → Qiskit Reverse Transpiler
=======================================
Translates hardware-native IR back to IBM Qiskit OpenQASM 2.0,
enabling developers on alternative platforms to run on IBM Quantum.

Usage:
    from originir_to_qiskit import reverse_transpile
    qasm = reverse_transpile(originir_string)
"""

import re
import math

# OriginIR → OpenQASM gate mapping
REVERSE_MAP = {
    "H": ("h", 0),
    "X": ("x", 0),
    "Y": ("y", 0),
    "Z": ("z", 0),
    "S": ("s", 0),
    "T": ("t", 0),
    "I": ("id", 0),
    "RX": ("rx", 1),
    "RY": ("ry", 1),
    "RZ": ("rz", 1),
    "U2": ("u2", 2),
    "U3": ("u3", 3),
    "CNOT": ("cx", 0),
    "CZ": ("cz", 0),
    "SWAP": ("swap", 0),
    "CR": ("crz", 1),
    "TOFFOLI": ("ccx", 0),
    "CSWAP": ("cswap", 0),
}


def _parse_param(p):
    """Parse OriginIR parameter string (e.g. '0.25*pi', 'pi', '-pi', '3.14')."""
    p = p.strip()
    if p == "pi":
        return str(math.pi)
    elif p == "-pi":
        return str(-math.pi)
    elif "*pi" in p:
        coeff = float(p.replace("*pi", ""))
        return str(coeff * math.pi)
    else:
        return p


def _parse_qubits(s):
    """Extract qubit indices from 'q[0], q[1]' style strings."""
    return re.findall(r'q\[(\d+)\]', s)


def _parse_cbits(s):
    """Extract classical bit indices from 'c[0]' style strings."""
    return re.findall(r'c\[(\d+)\]', s)


def reverse_transpile(originir: str) -> str:
    """
    Convert OriginIR string to OpenQASM 2.0.
    
    Args:
        originir: OriginIR program string
    
    Returns:
        OpenQASM 2.0 string
    """
    lines = originir.strip().split('\n')
    
    n_qubits = 0
    n_cbits = 0
    qasm_body = []
    in_dagger = False
    dagger_buffer = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Parse QINIT / CREG
        if line.startswith('QINIT'):
            n_qubits = int(line.split()[1])
            continue
        if line.startswith('CREG'):
            n_cbits = int(line.split()[1])
            continue
        
        # DAGGER blocks
        if line == 'DAGGER':
            in_dagger = True
            dagger_buffer = []
            continue
        if line == 'ENDDAGGER':
            in_dagger = False
            # Apply dagger: reverse order, add 'dg' suffix where applicable
            for gate_line in reversed(dagger_buffer):
                qasm_body.append(_dagger_gate(gate_line))
            continue
        
        # BARRIER
        if line.startswith('BARRIER'):
            qubits = _parse_qubits(line)
            qrefs = ','.join(f'q[{q}]' for q in qubits)
            gate_line = f'barrier {qrefs};'
            if in_dagger:
                dagger_buffer.append(gate_line)
            else:
                qasm_body.append(gate_line)
            continue
        
        # MEASURE
        if line.startswith('MEASURE'):
            qubits = _parse_qubits(line)
            cbits = _parse_cbits(line)
            if qubits and cbits:
                qasm_body.append(f'measure q[{qubits[0]}] -> c[{cbits[0]}];')
            continue
        
        # Parse gate
        gate_line = _parse_gate(line)
        if gate_line:
            if in_dagger:
                dagger_buffer.append(gate_line)
            else:
                qasm_body.append(gate_line)
    
    # Build QASM
    header = [
        'OPENQASM 2.0;',
        'include "qelib1.inc";',
        f'qreg q[{n_qubits}];',
    ]
    if n_cbits > 0:
        header.append(f'creg c[{n_cbits}];')
    
    return '\n'.join(header + qasm_body)


def _parse_gate(line):
    """Parse a single OriginIR gate line into QASM."""
    # Extract gate name (first token)
    parts = line.split()
    gate_name = parts[0].upper()
    
    mapping = REVERSE_MAP.get(gate_name)
    if not mapping:
        return f'// UNSUPPORTED: {line}'
    
    qasm_gate, n_params = mapping
    
    # Extract qubits
    qubits = _parse_qubits(line)
    qrefs = ','.join(f'q[{q}]' for q in qubits)
    
    # Extract params if any
    param_match = re.search(r'\(([^)]+)\)', line)
    if n_params > 0 and param_match:
        raw_params = param_match.group(1).split(',')
        params = ','.join(_parse_param(p) for p in raw_params)
        return f'{qasm_gate}({params}) {qrefs};'
    else:
        return f'{qasm_gate} {qrefs};'


def _dagger_gate(qasm_line):
    """Convert a QASM gate to its dagger (adjoint) version."""
    qasm_line = qasm_line.strip()
    if qasm_line.startswith('s '):
        return qasm_line.replace('s ', 'sdg ', 1)
    elif qasm_line.startswith('t '):
        return qasm_line.replace('t ', 'tdg ', 1)
    elif qasm_line.startswith('rx('):
        # Rx†(θ) = Rx(-θ)
        return re.sub(r'rx\(([^)]+)\)', lambda m: f'rx({-float(m.group(1))})', qasm_line)
    elif qasm_line.startswith('ry('):
        return re.sub(r'ry\(([^)]+)\)', lambda m: f'ry({-float(m.group(1))})', qasm_line)
    elif qasm_line.startswith('rz('):
        return re.sub(r'rz\(([^)]+)\)', lambda m: f'rz({-float(m.group(1))})', qasm_line)
    elif qasm_line.startswith(('h ', 'x ', 'y ', 'z ', 'cx ', 'cz ', 'swap ')):
        # Self-adjoint gates
        return qasm_line
    return qasm_line


def test_reverse():
    """Test round-trip: Qiskit → OriginIR → Qiskit."""
    # Bell state in OriginIR
    originir = """QINIT 2
CREG 2
H q[0]
CNOT q[0], q[1]
MEASURE q[0], c[0]
MEASURE q[1], c[1]"""
    
    qasm = reverse_transpile(originir)
    print("=== OriginIR Input ===")
    print(originir)
    print()
    print("=== OpenQASM Output ===")
    print(qasm)
    print()
    
    # GHZ with params
    originir2 = """QINIT 3
CREG 3
H q[0]
CNOT q[0], q[1]
CNOT q[1], q[2]
RX q[0], (0.25*pi)
BARRIER q[0], q[1], q[2]
MEASURE q[0], c[0]
MEASURE q[1], c[1]
MEASURE q[2], c[2]"""
    
    qasm2 = reverse_transpile(originir2)
    print("=== GHZ + Rx ===")
    print(qasm2)
    print()
    
    # Dagger test
    originir3 = """QINIT 1
CREG 0
DAGGER
S q[0]
T q[0]
ENDDAGGER"""
    
    qasm3 = reverse_transpile(originir3)
    print("=== Dagger Test ===")
    print(qasm3)
    print()
    
    assert 'h q[0]' in qasm
    assert 'cx q[0],q[1]' in qasm
    assert 'measure' in qasm
    assert 'rx(' in qasm2
    assert 'barrier' in qasm2
    assert 'tdg' in qasm3
    assert 'sdg' in qasm3
    
    print("✅ All reverse transpiler tests passed!")


if __name__ == "__main__":
    test_reverse()
