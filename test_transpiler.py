"""Tests for Qiskit → OriginIR transpiler."""
import math
import sys

def test_without_qiskit():
    """Test gate map and utilities without Qiskit installed."""
    from qiskit_to_originir import GATE_MAP, _format_params

    # Gate map completeness
    assert "h" in GATE_MAP
    assert "cx" in GATE_MAP
    assert "ccx" in GATE_MAP
    assert GATE_MAP["h"] == ("H", 0)
    assert GATE_MAP["cx"] == ("CNOT", 0)

    # Parameter formatting
    assert _format_params([math.pi]) == "pi"
    assert _format_params([math.pi / 2]) == "0.5*pi"
    assert _format_params([0]) == "0"
    assert _format_params([-math.pi]) == "-pi"
    assert _format_params([math.pi / 4]) == "0.25*pi"

    print("✅ Gate map and param formatting OK")


def test_with_qiskit():
    """Full transpilation test (requires Qiskit)."""
    try:
        from qiskit import QuantumCircuit
    except ImportError:
        print("⚠️  Qiskit not installed, skipping full test")
        return

    from qiskit_to_originir import transpile

    # Bell state
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])

    ir = transpile(qc)
    lines = ir.strip().split("\n")

    assert lines[0] == "QINIT 2"
    assert lines[1] == "CREG 2"
    assert "H q[0]" in ir
    assert "CNOT q[0], q[1]" in ir
    assert "MEASURE q[0], c[0]" in ir
    assert "MEASURE q[1], c[1]" in ir
    print("✅ Bell state transpilation OK")

    # Parameterized gates
    qc2 = QuantumCircuit(1)
    qc2.rx(math.pi / 4, 0)
    qc2.rz(math.pi, 0)

    ir2 = transpile(qc2)
    assert "RX q[0], (0.25*pi)" in ir2
    assert "RZ q[0], (pi)" in ir2
    print("✅ Parameterized gates OK")

    # Dagger gates
    qc3 = QuantumCircuit(1)
    qc3.sdg(0)
    qc3.tdg(0)

    ir3 = transpile(qc3)
    assert "DAGGER" in ir3
    assert "ENDDAGGER" in ir3
    print("✅ Dagger gates OK")

    # GHZ state (3-qubit)
    qc4 = QuantumCircuit(3, 3)
    qc4.h(0)
    qc4.cx(0, 1)
    qc4.cx(1, 2)
    qc4.barrier()
    qc4.measure([0, 1, 2], [0, 1, 2])

    ir4 = transpile(qc4)
    assert "QINIT 3" in ir4
    assert "BARRIER" in ir4
    assert ir4.count("MEASURE") == 3
    print("✅ GHZ state transpilation OK")

    # Toffoli
    qc5 = QuantumCircuit(3)
    qc5.ccx(0, 1, 2)
    ir5 = transpile(qc5)
    assert "TOFFOLI q[0], q[1], q[2]" in ir5
    print("✅ Toffoli gate OK")

    print("\n🎉 All transpiler tests passed!")


if __name__ == "__main__":
    test_without_qiskit()
    test_with_qiskit()
