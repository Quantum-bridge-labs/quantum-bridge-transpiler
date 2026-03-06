# ⚛️ Quantum Bridge Transpiler

**Write circuits in Qiskit. Run them on any quantum hardware.**

A universal quantum circuit transpiler that converts IBM Qiskit / OpenQASM 2.0 circuits into hardware-native instruction sets. One function call, sub-3ms.

## Quick Start

```bash
pip install qiskit
```

```python
from qiskit import QuantumCircuit
from qiskit_to_originir import transpile

# Build a Bell state in Qiskit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

# Transpile to hardware IR
print(transpile(qc))
```

**Output:**
```
QINIT 2
CREG 2
H q[0]
CNOT q[0], q[1]
MEASURE q[0], c[0]
MEASURE q[1], c[1]
```

## Supported Gates (20+)

| Category | Gates |
|----------|-------|
| Single-qubit | H, X, Y, Z, S, T, S†, T†, I |
| Parameterized | Rx(θ), Ry(θ), Rz(θ), U1, U2, U3 |
| Two-qubit | CNOT/CX, CZ, SWAP, CR |
| Three-qubit | Toffoli (CCX), Fredkin (CSWAP) |
| Operations | MEASURE, BARRIER |

Angles are automatically formatted as π-fractions for readability (`0.25*pi` instead of `0.7853981...`).

## From OpenQASM

```python
from qiskit_to_originir import transpile_file

qasm = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
measure q[2] -> c[2];
"""

print(transpile_file(qasm))
```

## API Service

Don't want to self-host? Use our managed API:

```bash
curl -X POST https://transpiler.gpupulse.dev/api/transpile \
  -H "Content-Type: application/json" \
  -d '{"qasm": "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];"}'
```

**Live demo with visual circuit builder:** [transpiler.gpupulse.dev](https://transpiler.gpupulse.dev)

## Tests

```bash
python test_transpiler.py
```

## Why?

Qiskit is the global standard for writing quantum circuits. But not all quantum hardware speaks the same language. Quantum Bridge translates your circuits so you can run them anywhere — without rewriting a single line.

## License

MIT

---

Built by [GPUPulse](https://gpupulse.dev)
