from __future__ import annotations

from scripts.beta_readiness_gate import GateResult, gate_exit_code, summarize


def test_gate_exit_code_pass() -> None:
    results = [GateResult(name="a", status="PASS", detail="ok", elapsed_sec=0.1)]
    assert gate_exit_code(results) == 0


def test_gate_exit_code_fail() -> None:
    results = [GateResult(name="a", status="FAIL", detail="no", elapsed_sec=0.1)]
    assert gate_exit_code(results) == 1


def test_gate_summary_contains_table() -> None:
    report = summarize([GateResult(name="contract", status="PASS", detail="ok", elapsed_sec=0.0)])
    assert "CHECK" in report
    assert "contract" in report
