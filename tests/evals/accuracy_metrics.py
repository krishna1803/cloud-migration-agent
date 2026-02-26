"""
Accuracy Metrics and Invariant Checker for the Cloud Migration Agent Evaluation Harness.

Classes:
  InvariantChecker   - Evaluates boolean invariants against a MigrationState
  AccuracyMetrics    - Aggregates pass/fail counts into summary statistics
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class InvariantResult:
    """Result of a single invariant check."""
    invariant_id: str
    description: str
    phase: str
    passed: bool
    field_value: Any = None
    error: Optional[str] = None


@dataclass
class PhaseMetrics:
    """Pass/fail counts for a single workflow phase."""
    phase: str
    total: int = 0
    passed: int = 0
    failed: int = 0

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


@dataclass
class ScenarioMetrics:
    """Aggregated metrics for one scenario run."""
    scenario_id: str
    total_invariants: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    phase_breakdown: Dict[str, PhaseMetrics] = field(default_factory=dict)
    results: List[InvariantResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_invariants if self.total_invariants else 0.0

    def summary(self) -> str:
        lines = [
            f"Scenario: {self.scenario_id}",
            f"  Total invariants : {self.total_invariants}",
            f"  Passed           : {self.passed}",
            f"  Failed           : {self.failed}",
            f"  Errors           : {self.errors}",
            f"  Pass rate        : {self.pass_rate:.1%}",
        ]
        if self.phase_breakdown:
            lines.append("  By phase:")
            for pm in sorted(self.phase_breakdown.values(), key=lambda p: p.phase):
                lines.append(
                    f"    {pm.phase:<22} {pm.passed}/{pm.total} "
                    f"({pm.pass_rate:.0%})"
                )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# InvariantChecker
# ---------------------------------------------------------------------------

class InvariantChecker:
    """
    Evaluates a list of invariant dicts against a MigrationState.

    Invariant dict schema:
      id          - unique identifier
      description - human-readable description
      phase       - workflow phase label (for reporting)
      field       - dot-separated path into MigrationState (e.g. "discovery.discovered_services")
      check       - Python expression using `value` as the resolved field value
    """

    def check_all(
        self,
        state: Any,
        invariants: List[Dict[str, Any]],
    ) -> List[InvariantResult]:
        results = []
        for inv in invariants:
            result = self._check_one(state, inv)
            results.append(result)
        return results

    def _check_one(self, state: Any, inv: Dict[str, Any]) -> InvariantResult:
        inv_id = inv.get("id", "unknown")
        description = inv.get("description", "")
        phase = inv.get("phase", "all")
        field_path = inv.get("field", "")
        check_expr = inv.get("check", "True")

        # Safe builtins available in invariant check expressions
        _safe_builtins = {
            "len": len, "bool": bool, "str": str, "int": int, "float": float,
            "list": list, "dict": dict, "set": set, "any": any, "all": all,
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "isinstance": isinstance, "hasattr": hasattr,
            "None": None, "True": True, "False": False,
        }
        try:
            value = self._resolve_field(state, field_path)
            passed = bool(eval(  # noqa: S307
                check_expr,
                {"value": value, "__builtins__": _safe_builtins},
            ))
            return InvariantResult(
                invariant_id=inv_id,
                description=description,
                phase=phase,
                passed=passed,
                field_value=value,
            )
        except Exception as exc:
            return InvariantResult(
                invariant_id=inv_id,
                description=description,
                phase=phase,
                passed=False,
                error=str(exc),
            )

    @staticmethod
    def _resolve_field(state: Any, field_path: str) -> Any:
        """Traverse a dot-separated attribute path from root state."""
        parts = field_path.split(".")
        obj = state
        for part in parts:
            if obj is None:
                return None
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                obj = getattr(obj, part, None)
        return obj


# ---------------------------------------------------------------------------
# AccuracyMetrics
# ---------------------------------------------------------------------------

class AccuracyMetrics:
    """
    Aggregates InvariantResult lists from multiple scenario runs into
    overall and per-phase accuracy statistics.
    """

    def compute(
        self,
        scenario_id: str,
        results: List[InvariantResult],
    ) -> ScenarioMetrics:
        metrics = ScenarioMetrics(
            scenario_id=scenario_id,
            total_invariants=len(results),
        )

        for r in results:
            metrics.results.append(r)

            # Update phase breakdown
            if r.phase not in metrics.phase_breakdown:
                metrics.phase_breakdown[r.phase] = PhaseMetrics(phase=r.phase)
            pm = metrics.phase_breakdown[r.phase]
            pm.total += 1

            if r.error:
                metrics.errors += 1
                pm.failed += 1
            elif r.passed:
                metrics.passed += 1
                pm.passed += 1
            else:
                metrics.failed += 1
                pm.failed += 1

        return metrics

    @staticmethod
    def aggregate(all_metrics: List[ScenarioMetrics]) -> Dict[str, Any]:
        """Produce a cross-scenario summary dict."""
        total = sum(m.total_invariants for m in all_metrics)
        passed = sum(m.passed for m in all_metrics)
        failed = sum(m.failed for m in all_metrics)
        errors = sum(m.errors for m in all_metrics)
        return {
            "scenarios": len(all_metrics),
            "total_invariants": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "overall_pass_rate": passed / total if total else 0.0,
        }
