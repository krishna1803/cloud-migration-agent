"""
Evaluation scenario registry.

ALL_SCENARIOS maps scenario IDs to their module definitions.
Each scenario module exposes:
  SCENARIO_ID   - str identifier
  INPUT         - dict of MigrationState constructor kwargs
  INVARIANTS    - list of invariant dicts checked by InvariantChecker
"""

from tests.evals.scenarios.aws_eks_rds_scenario import (
    SCENARIO_ID as AWS_EKS_RDS_ID,
    INPUT as AWS_EKS_RDS_INPUT,
    INVARIANTS as AWS_EKS_RDS_INVARIANTS,
)
from tests.evals.scenarios.aws_webapp_scenario import (
    SCENARIO_ID as AWS_WEBAPP_ID,
    INPUT as AWS_WEBAPP_INPUT,
    INVARIANTS as AWS_WEBAPP_INVARIANTS,
)
from tests.evals.scenarios.azure_vm_sql_scenario import (
    SCENARIO_ID as AZURE_VM_SQL_ID,
    INPUT as AZURE_VM_SQL_INPUT,
    INVARIANTS as AZURE_VM_SQL_INVARIANTS,
)
from tests.evals.scenarios.security_compliance_scenario import (
    SCENARIO_ID as SECURITY_COMPLIANCE_ID,
    INPUT as SECURITY_COMPLIANCE_INPUT,
    INVARIANTS as SECURITY_COMPLIANCE_INVARIANTS,
)

ALL_SCENARIOS = {
    AWS_EKS_RDS_ID: {
        "input": AWS_EKS_RDS_INPUT,
        "invariants": AWS_EKS_RDS_INVARIANTS,
    },
    AWS_WEBAPP_ID: {
        "input": AWS_WEBAPP_INPUT,
        "invariants": AWS_WEBAPP_INVARIANTS,
    },
    AZURE_VM_SQL_ID: {
        "input": AZURE_VM_SQL_INPUT,
        "invariants": AZURE_VM_SQL_INVARIANTS,
    },
    SECURITY_COMPLIANCE_ID: {
        "input": SECURITY_COMPLIANCE_INPUT,
        "invariants": SECURITY_COMPLIANCE_INVARIANTS,
    },
}

__all__ = ["ALL_SCENARIOS"]
