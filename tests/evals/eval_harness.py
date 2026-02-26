"""
Evaluation Harness for the Cloud Migration Agent Platform v4.2.0.

Runs each registered scenario through the Phase 1 discovery nodes
(and optionally further phases) and checks all invariants via InvariantChecker.

Usage:
    conda run -n claudecloudmigration python tests/evals/eval_harness.py
    conda run -n claudecloudmigration python tests/evals/eval_harness.py --scenario aws_eks_rds
    conda run -n claudecloudmigration python tests/evals/eval_harness.py --phase discovery
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

from src.models.state_schema import MigrationState, create_migration_state
from tests.evals.accuracy_metrics import AccuracyMetrics, InvariantChecker, ScenarioMetrics
from tests.evals.scenarios import ALL_SCENARIOS


# ---------------------------------------------------------------------------
# Phase runner registry
# Maps phase names to callables that accept and return MigrationState
# ---------------------------------------------------------------------------

def _run_discovery(state: MigrationState) -> MigrationState:
    from src.agents.phase1_discovery import (
        intake_plan,
        kb_enrich_discovery,
        document_ingestion,
        bom_analysis,
        extract_evidence,
        gap_detection,
        security_posture_config,
        dependency_analysis_config,
    )
    state = intake_plan(state)
    state = kb_enrich_discovery(state)
    state = document_ingestion(state)
    state = bom_analysis(state)
    state = extract_evidence(state)
    state = gap_detection(state)
    state = security_posture_config(state)
    state = dependency_analysis_config(state)
    return state


def _run_analysis(state: MigrationState) -> MigrationState:
    from src.agents.phase2_analysis import (
        reconstruct_current_state,
        service_mapping,
        resource_sizing,
        cost_estimation,
    )
    state = reconstruct_current_state(state)
    state = service_mapping(state)
    state = resource_sizing(state)
    state = cost_estimation(state)
    return state


def _run_design(state: MigrationState) -> MigrationState:
    from src.agents.phase3_design import (
        formal_architecture_modeling,
        component_definition,
        dependency_mapping,
        topological_sort_deployment,
        diagram_generation,
        design_phase_complete,
    )
    state = formal_architecture_modeling(state)
    state = component_definition(state)
    state = dependency_mapping(state)
    state = topological_sort_deployment(state)
    state = diagram_generation(state)
    state = design_phase_complete(state)
    return state


def _run_implementation(state: MigrationState) -> MigrationState:
    from src.agents.phase5_implementation import (
        strategy_selection,
        terraform_module_definition,
        terraform_code_generation,
        code_validation,
        project_export,
    )
    state = strategy_selection(state)
    state = terraform_module_definition(state)
    state = terraform_code_generation(state)
    state = code_validation(state)
    state = project_export(state)
    return state


def _run_deployment(state: MigrationState) -> MigrationState:
    from src.agents.phase6_deployment import (
        pre_deployment_validation,
        generate_deployment_report,
        package_deliverables,
        data_lineage,
        deployment_complete,
    )
    state = pre_deployment_validation(state)
    state = generate_deployment_report(state)
    state = package_deliverables(state)
    state = data_lineage(state)
    state = deployment_complete(state)
    return state


PHASE_RUNNERS = {
    "discovery": _run_discovery,
    "analysis": _run_analysis,
    "design": _run_design,
    "implementation": _run_implementation,
    "deployment": _run_deployment,
}

# Ordered list of phases executed when running "all"
ALL_PHASES_ORDERED = ["discovery", "analysis", "design", "implementation", "deployment"]


# ---------------------------------------------------------------------------
# EvaluationHarness
# ---------------------------------------------------------------------------

class EvaluationHarness:
    """
    Orchestrates evaluation runs across scenarios and phases.

    For each scenario:
      1. Construct a MigrationState from scenario INPUT
      2. Run selected phases sequentially
      3. Check all INVARIANTS via InvariantChecker
      4. Collect ScenarioMetrics via AccuracyMetrics
    """

    def __init__(
        self,
        scenarios: Optional[List[str]] = None,
        phases: Optional[List[str]] = None,
        stop_on_failure: bool = False,
    ):
        self.scenario_filter = set(scenarios) if scenarios else None
        self.phase_filter = phases or ALL_PHASES_ORDERED
        self.stop_on_failure = stop_on_failure
        self._checker = InvariantChecker()
        self._metrics = AccuracyMetrics()

    def run(self) -> List[ScenarioMetrics]:
        all_results: List[ScenarioMetrics] = []
        scenarios = {
            sid: data
            for sid, data in ALL_SCENARIOS.items()
            if self.scenario_filter is None or sid in self.scenario_filter
        }

        if not scenarios:
            print(f"No scenarios matched filter: {self.scenario_filter}")
            return []

        print(f"\n{'='*60}")
        print(f"Cloud Migration Agent — Evaluation Harness v4.2.0")
        print(f"Scenarios: {len(scenarios)}  |  Phases: {self.phase_filter}")
        print(f"{'='*60}\n")

        for scenario_id, scenario_data in scenarios.items():
            print(f"▶ Running scenario: {scenario_id}")
            t0 = time.time()
            try:
                result = self._run_scenario(scenario_id, scenario_data)
            except Exception as exc:
                print(f"  ✗ Scenario crashed: {exc}")
                if self.stop_on_failure:
                    raise
                continue

            elapsed = time.time() - t0
            print(f"  Done in {elapsed:.1f}s — "
                  f"{result.passed}/{result.total_invariants} invariants passed "
                  f"({result.pass_rate:.0%})")
            all_results.append(result)

        self._print_summary(all_results)
        return all_results

    def _run_scenario(
        self, scenario_id: str, scenario_data: Dict[str, Any]
    ) -> ScenarioMetrics:
        inp = scenario_data["input"]
        invariants = scenario_data["invariants"]

        # Build initial state
        migration_id = f"eval-{scenario_id[:12]}-{uuid.uuid4().hex[:6]}"
        state = create_migration_state(
            migration_id=migration_id,
            user_context=inp.get("user_context", ""),
            source_provider=inp.get("source_provider", "AWS"),
            target_region=inp.get("target_region", "us-ashburn-1"),
        )
        state.uploaded_documents = inp.get("uploaded_documents", [])
        state.bom_file = inp.get("bom_file")

        # Apply pre-configured dependency constraints if provided
        if "dependency_constraints" in inp:
            state.dependency_constraints = inp["dependency_constraints"]

        # Execute phases
        for phase in self.phase_filter:
            runner = PHASE_RUNNERS.get(phase)
            if runner is None:
                print(f"  ⚠ Unknown phase '{phase}', skipping")
                continue
            try:
                state = runner(state)
            except Exception as exc:
                print(f"  ⚠ Phase '{phase}' raised exception: {exc}")
                state.errors.append(f"Phase {phase} error: {str(exc)}")

        # Evaluate invariants
        inv_results = self._checker.check_all(state, invariants)

        # Report per-invariant failures
        failures = [r for r in inv_results if not r.passed]
        if failures:
            print(f"  Failed invariants ({len(failures)}):")
            for f in failures[:5]:
                err_info = f" [error: {f.error}]" if f.error else ""
                print(f"    ✗ [{f.invariant_id}] {f.description}{err_info}")
            if len(failures) > 5:
                print(f"    ... and {len(failures) - 5} more")

        return self._metrics.compute(scenario_id, inv_results)

    @staticmethod
    def _print_summary(all_results: List[ScenarioMetrics]) -> None:
        if not all_results:
            return
        agg = AccuracyMetrics.aggregate(all_results)
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"  Scenarios run    : {agg['scenarios']}")
        print(f"  Total invariants : {agg['total_invariants']}")
        print(f"  Passed           : {agg['passed']}")
        print(f"  Failed           : {agg['failed']}")
        print(f"  Errors           : {agg['errors']}")
        print(f"  Overall pass rate: {agg['overall_pass_rate']:.1%}")
        print(f"{'='*60}\n")

        for m in all_results:
            status = "✅" if m.pass_rate >= 0.8 else "⚠️ " if m.pass_rate >= 0.5 else "❌"
            print(f"  {status} {m.scenario_id:<30} {m.passed}/{m.total_invariants} ({m.pass_rate:.0%})")
        print()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cloud Migration Agent Evaluation Harness v4.2.0"
    )
    parser.add_argument(
        "--scenario",
        nargs="*",
        help="Scenario IDs to run (default: all). "
             "Options: aws_eks_rds, aws_webapp, azure_vm_sql, security_compliance",
    )
    parser.add_argument(
        "--phase",
        nargs="*",
        choices=list(PHASE_RUNNERS.keys()),
        help="Phases to execute per scenario (default: all phases in order)",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop on first scenario crash",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    harness = EvaluationHarness(
        scenarios=args.scenario,
        phases=args.phase,
        stop_on_failure=args.stop_on_failure,
    )
    results = harness.run()

    # Exit 1 if any scenario has < 50% pass rate
    if any(r.pass_rate < 0.5 for r in results):
        sys.exit(1)
