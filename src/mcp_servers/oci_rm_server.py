"""MCP Server 10: OCI Resource Manager (oci_rm).

Uses the OCI Python SDK to create stacks, run plans/applies, and
retrieve job status from OCI Resource Manager (managed Terraform).

Falls back gracefully to a mock implementation when OCI credentials
are not configured (e.g. development / CI environments).

Reference: https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm
"""
import base64
import io
import time
import uuid
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
try:
    import oci
    _OCI_SDK_AVAILABLE = True
except ImportError:
    _OCI_SDK_AVAILABLE = False


def _build_oci_config() -> Optional[Dict]:
    """Load OCI config from ~/.oci/config or env vars. Returns None on failure."""
    if not _OCI_SDK_AVAILABLE:
        return None
    try:
        from src.utils.config import config as app_cfg
        oci_cfg = oci.config.from_file()
        # Allow env-var overrides
        if app_cfg.oci.region:
            oci_cfg["region"] = app_cfg.oci.region
        if app_cfg.oci.tenancy_id:
            oci_cfg["tenancy"] = app_cfg.oci.tenancy_id
        if app_cfg.oci.user_id:
            oci_cfg["user"] = app_cfg.oci.user_id
        if app_cfg.oci.fingerprint:
            oci_cfg["fingerprint"] = app_cfg.oci.fingerprint
        if app_cfg.oci.private_key_path:
            oci_cfg["key_file"] = app_cfg.oci.private_key_path
        oci.config.validate_config(oci_cfg)
        return oci_cfg
    except Exception:
        return None


def _terraform_to_zip_b64(terraform_config: str, extra_files: Optional[Dict[str, str]] = None) -> str:
    """
    Package Terraform HCL string(s) into an in-memory ZIP archive,
    then Base64-encode it for the OCI Resource Manager API.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.tf", terraform_config)
        for fname, content in (extra_files or {}).items():
            zf.writestr(fname, content)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# ---------------------------------------------------------------------------
class OCIResourceManagerServer:
    SERVER_NAME = "oci_rm"
    VERSION = "2.0.0"

    def __init__(self):
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0.0

        # In-memory mock state (used when SDK unavailable or as local cache)
        self._stacks: Dict[str, Dict] = {}
        self._jobs:   Dict[str, Dict] = {}

        self._oci_config = _build_oci_config()
        self._rm_client = None
        self._use_real_sdk = False

        if self._oci_config and _OCI_SDK_AVAILABLE:
            try:
                self._rm_client = oci.resource_manager.ResourceManagerClient(self._oci_config)
                self._use_real_sdk = True
            except Exception:
                self._use_real_sdk = False

    def _record(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success:
            self._success_count += 1
        self._total_latency_ms += latency_ms

    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    # ──────────────────────────────────────────────────────────────────────────
    # REAL SDK METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def _real_create_stack(
        self,
        stack_name: str,
        terraform_config: str,
        compartment_id: str,
        variables: Optional[Dict] = None,
        description: str = "",
        extra_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        zip_b64 = _terraform_to_zip_b64(terraform_config, extra_files)
        details = oci.resource_manager.models.CreateStackDetails(
            compartment_id=compartment_id,
            display_name=stack_name,
            description=description or f"Migration stack: {stack_name}",
            config_source=oci.resource_manager.models.CreateZipUploadConfigSourceDetails(
                config_source_type="ZIP_UPLOAD",
                zip_file_base64_encoded=zip_b64,
            ),
            variables=variables or {},
            terraform_version="1.2.x",
            freeform_tags={"created-by": "cloud-migration-agent", "version": "4.0.0"},
        )
        resp = self._rm_client.create_stack(create_stack_details=details)
        stack = resp.data
        return {
            "stack_id":        stack.id,
            "stack_name":      stack.display_name,
            "compartment_id":  stack.compartment_id,
            "lifecycle_state": stack.lifecycle_state,
            "time_created":    str(stack.time_created),
            "variables":       stack.variables or {},
        }

    def _real_create_job(
        self,
        stack_id: str,
        operation: str,
        plan_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if operation == "PLAN":
            op_details = oci.resource_manager.models.CreatePlanJobOperationDetails(
                operation="PLAN"
            )
        elif operation == "APPLY":
            if plan_job_id:
                op_details = oci.resource_manager.models.CreateApplyJobOperationDetails(
                    operation="APPLY",
                    execution_plan_strategy="FROM_PLAN_JOB_ID",
                    execution_plan_job_id=plan_job_id,
                )
            else:
                op_details = oci.resource_manager.models.CreateApplyJobOperationDetails(
                    operation="APPLY",
                    execution_plan_strategy="AUTO_APPROVED",
                )
        elif operation == "DESTROY":
            op_details = oci.resource_manager.models.CreateDestroyJobOperationDetails(
                operation="DESTROY",
                execution_plan_strategy="AUTO_APPROVED",
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")

        resp = self._rm_client.create_job(
            create_job_details=oci.resource_manager.models.CreateJobDetails(
                stack_id=stack_id,
                display_name=f"{operation.lower()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                job_operation_details=op_details,
            )
        )
        job = resp.data
        return {
            "job_id":          job.id,
            "stack_id":        job.stack_id,
            "operation":       job.operation,
            "lifecycle_state": job.lifecycle_state,
            "time_created":    str(job.time_created),
        }

    def _real_get_job(self, job_id: str) -> Dict[str, Any]:
        resp = self._rm_client.get_job(job_id=job_id)
        job = resp.data
        result = {
            "job_id":          job.id,
            "stack_id":        job.stack_id,
            "operation":       job.operation,
            "lifecycle_state": job.lifecycle_state,
            "time_created":    str(job.time_created),
        }
        if job.time_finished:
            result["time_finished"] = str(job.time_finished)
        if hasattr(job, "failure_details") and job.failure_details:
            result["failure_details"] = job.failure_details
        return result

    def _real_get_job_logs(self, job_id: str) -> List[Dict[str, Any]]:
        resp = self._rm_client.get_job_logs(job_id=job_id)
        logs = []
        for entry in resp.data:
            logs.append({
                "timestamp": str(entry.timestamp),
                "level":     entry.level,
                "message":   entry.message,
                "type":      entry.type,
            })
        return logs

    def _real_get_job_tf_state(self, job_id: str) -> str:
        resp = self._rm_client.get_job_tf_state(job_id=job_id)
        return resp.data.decode("utf-8") if isinstance(resp.data, bytes) else str(resp.data)

    def _real_list_stacks(self, compartment_id: str) -> List[Dict[str, Any]]:
        resp = self._rm_client.list_stacks(compartment_id=compartment_id)
        results = []
        for s in resp.data.items:
            results.append({
                "stack_id":        s.id,
                "display_name":    s.display_name,
                "lifecycle_state": s.lifecycle_state,
                "time_created":    str(s.time_created),
            })
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # MOCK METHODS (fallback / offline)
    # ──────────────────────────────────────────────────────────────────────────

    def _mock_create_stack(
        self, stack_name: str, terraform_config: str,
        compartment_id: str, variables: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        stack_id = f"ocid1.ormstack.oc1.iad.{uuid.uuid4().hex[:20]}"
        stack = {
            "stack_id":        stack_id,
            "stack_name":      stack_name,
            "compartment_id":  compartment_id,
            "lifecycle_state": "ACTIVE",
            "time_created":    self._now(),
            "variables":       variables or {},
            "terraform_preview": terraform_config[:500] + ("…" if len(terraform_config) > 500 else ""),
        }
        self._stacks[stack_id] = stack
        return stack

    def _mock_create_job(
        self, stack_id: str, operation: str, plan_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        job_id = f"ocid1.ormjob.oc1.iad.{uuid.uuid4().hex[:20]}"
        job = {
            "job_id":          job_id,
            "stack_id":        stack_id,
            "operation":       operation,
            "lifecycle_state": "ACCEPTED",
            "time_created":    self._now(),
        }
        if plan_job_id:
            job["plan_job_id"] = plan_job_id
        self._jobs[job_id] = job
        return job

    def _mock_get_job(self, job_id: str) -> Dict[str, Any]:
        job = dict(self._jobs.get(job_id, {
            "job_id": job_id, "lifecycle_state": "SUCCEEDED", "operation": "PLAN",
        }))
        # Simulate progression
        if job.get("lifecycle_state") in ("ACCEPTED", "IN_PROGRESS"):
            job["lifecycle_state"] = "SUCCEEDED"
            job["time_finished"] = self._now()
            self._jobs[job_id] = job
        return job

    def _mock_get_job_logs(self, job_id: str, operation: str = "APPLY") -> List[Dict[str, Any]]:
        now = self._now()
        op = operation.upper()
        if op == "PLAN":
            messages = [
                "Terraform initialized in the directory.",
                "Refreshing state…",
                "  # oci_core_vcn.main will be created",
                "  + cidr_block = \"10.0.0.0/16\"",
                "  # oci_core_subnet.public will be created",
                "  # oci_core_subnet.private will be created",
                "  # oci_core_internet_gateway.main will be created",
                "  # oci_core_nat_gateway.main will be created",
                "  # oci_core_instance.app_server[0] will be created",
                "  # oci_load_balancer_load_balancer.main will be created",
                "Plan: 10 to add, 0 to change, 0 to destroy.",
            ]
        elif op == "APPLY":
            messages = [
                "Terraform initialized.",
                "oci_core_vcn.main: Creating…",
                "oci_core_vcn.main: Creation complete after 2s [id=ocid1.vcn…]",
                "oci_core_subnet.public: Creating…",
                "oci_core_subnet.private: Creating…",
                "oci_core_internet_gateway.main: Creating…",
                "oci_core_nat_gateway.main: Creating…",
                "oci_core_subnet.public: Creation complete after 3s",
                "oci_core_subnet.private: Creation complete after 3s",
                "oci_core_instance.app_server[0]: Creating…",
                "oci_core_instance.app_server[0]: Still creating… [30s elapsed]",
                "oci_core_instance.app_server[0]: Creation complete after 62s",
                "oci_load_balancer_load_balancer.main: Creating…",
                "oci_load_balancer_load_balancer.main: Creation complete after 25s",
                "Apply complete! Resources: 10 added, 0 changed, 0 destroyed.",
            ]
        else:
            messages = [f"Job {op} completed successfully."]

        return [{"timestamp": now, "level": "INFO", "message": m, "type": "TERRAFORM_CONSOLE"} for m in messages]

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    def create_stack(
        self,
        stack_name: str,
        terraform_config: str,
        compartment_id: str = "",
        variables: Optional[Dict] = None,
        description: str = "",
        extra_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create an OCI Resource Manager stack from Terraform HCL."""
        t0 = time.time()
        try:
            if self._use_real_sdk:
                if not compartment_id:
                    from src.utils.config import config
                    compartment_id = config.oci.compartment_id
                stack = self._real_create_stack(
                    stack_name, terraform_config, compartment_id, variables, description, extra_files
                )
                mode = "real"
            else:
                stack = self._mock_create_stack(stack_name, terraform_config, compartment_id, variables)
                mode = "mock"

            self._record((time.time() - t0) * 1000)
            return {"stack_id": stack["stack_id"], "stack": stack, "status": "created", "mode": mode}
        except Exception as exc:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": str(exc), "status": "failed"}

    def plan_stack(self, stack_id: str) -> Dict[str, Any]:
        """Create a PLAN job for the given stack."""
        t0 = time.time()
        try:
            if self._use_real_sdk:
                job = self._real_create_job(stack_id, "PLAN")
                mode = "real"
            else:
                job = self._mock_create_job(stack_id, "PLAN")
                # Immediately show plan output in mock mode
                job["plan_output"] = "\n".join(
                    m["message"] for m in self._mock_get_job_logs(job["job_id"], "PLAN")
                )
                job["lifecycle_state"] = "SUCCEEDED"
                self._jobs[job["job_id"]] = job
                mode = "mock"

            self._record((time.time() - t0) * 1000)
            return {
                "job_id": job["job_id"],
                "job": job,
                "plan_output": job.get("plan_output", ""),
                "mode": mode,
            }
        except Exception as exc:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": str(exc), "status": "failed"}

    def apply_stack(
        self,
        stack_id: str,
        plan_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an APPLY job (optionally referencing a previous plan job)."""
        t0 = time.time()
        try:
            if self._use_real_sdk:
                job = self._real_create_job(stack_id, "APPLY", plan_job_id)
                mode = "real"
            else:
                job = self._mock_create_job(stack_id, "APPLY", plan_job_id)
                job["lifecycle_state"] = "IN_PROGRESS"
                self._jobs[job["job_id"]] = job
                mode = "mock"

            self._record((time.time() - t0) * 1000)
            return {"job_id": job["job_id"], "job": job, "status": "IN_PROGRESS", "mode": mode}
        except Exception as exc:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": str(exc), "status": "failed"}

    def destroy_stack(self, stack_id: str) -> Dict[str, Any]:
        """Create a DESTROY job for the given stack."""
        t0 = time.time()
        try:
            if self._use_real_sdk:
                job = self._real_create_job(stack_id, "DESTROY")
                mode = "real"
            else:
                job = self._mock_create_job(stack_id, "DESTROY")
                mode = "mock"

            self._record((time.time() - t0) * 1000)
            return {"job_id": job["job_id"], "job": job, "status": "IN_PROGRESS", "mode": mode}
        except Exception as exc:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": str(exc), "status": "failed"}

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a Resource Manager job."""
        t0 = time.time()
        try:
            if self._use_real_sdk:
                job = self._real_get_job(job_id)
                mode = "real"
            else:
                job = self._mock_get_job(job_id)
                mode = "mock"

            self._record((time.time() - t0) * 1000)
            return {"job_id": job_id, "job": job, "mode": mode}
        except Exception as exc:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": str(exc)}

    def get_job_logs(self, job_id: str) -> Dict[str, Any]:
        """Retrieve execution logs for a Resource Manager job."""
        t0 = time.time()
        try:
            if self._use_real_sdk:
                logs = self._real_get_job_logs(job_id)
                mode = "real"
            else:
                # Guess operation from local cache
                op = self._jobs.get(job_id, {}).get("operation", "APPLY")
                logs = self._mock_get_job_logs(job_id, op)
                mode = "mock"

            self._record((time.time() - t0) * 1000)
            return {"job_id": job_id, "logs": logs, "log_count": len(logs), "mode": mode}
        except Exception as exc:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": str(exc), "logs": []}

    def list_stacks(self, compartment_id: str = "") -> Dict[str, Any]:
        """List all OCI Resource Manager stacks in a compartment."""
        t0 = time.time()
        try:
            if self._use_real_sdk:
                if not compartment_id:
                    from src.utils.config import config
                    compartment_id = config.oci.compartment_id
                stacks = self._real_list_stacks(compartment_id)
                mode = "real"
            else:
                stacks = list(self._stacks.values())
                mode = "mock"

            self._record((time.time() - t0) * 1000)
            return {"stacks": stacks, "count": len(stacks), "mode": mode}
        except Exception as exc:
            self._record((time.time() - t0) * 1000, success=False)
            return {"error": str(exc), "stacks": []}

    def get_health_metrics(self) -> Dict[str, Any]:
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server":           self.SERVER_NAME,
            "version":          self.VERSION,
            "total_calls":      self._call_count,
            "success_rate":     round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms":   round(avg, 2),
            "status":           "healthy",
            "sdk_available":    _OCI_SDK_AVAILABLE,
            "real_sdk_active":  self._use_real_sdk,
            "mode":             "real" if self._use_real_sdk else "mock",
            "stacks_cached":    len(self._stacks),
            "jobs_cached":      len(self._jobs),
        }


oci_rm_server = OCIResourceManagerServer()
