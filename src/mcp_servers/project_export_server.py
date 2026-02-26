"""MCP Server: Project Export/Import (mcp_project_export).

Exports Terraform projects as ZIP archives for external editing and handles
re-import with change detection.

Tools (3):
  export_as_zip    - Export project as downloadable ZIP archive
  export_metadata  - Export project metadata and manifest
  import_project   - Import a modified project with change detection
"""
import base64
import hashlib
import io
import json
import os
import time
import zipfile
from typing import Any, Dict, List, Optional


class ProjectExportServer:
    """Project Export/Import MCP Server."""

    SERVER_NAME = "mcp_project_export"
    VERSION = "1.0.0"

    def __init__(self, export_dir: str = "exports"):
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)
        self._call_count = 0
        self._success_count = 0
        self._total_latency_ms = 0.0
        # In-memory store for exported manifests (keyed by export_id)
        self._manifests: Dict[str, Dict] = {}

    def _record(self, latency_ms: float, success: bool = True):
        self._call_count += 1
        if success:
            self._success_count += 1
        self._total_latency_ms += latency_ms

    def _file_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def export_as_zip(
        self,
        project_name: str,
        files: Dict[str, str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Export a Terraform project as a downloadable ZIP archive.

        Creates a ZIP containing all provided files plus a project manifest.
        The ZIP is base64-encoded for safe transport over JSON APIs.

        Args:
            project_name: Name used for the archive filename and root folder
            files: Dict of {filename: content} for all Terraform files
                   e.g. {'main.tf': '...', 'variables.tf': '...', 'outputs.tf': '...'}
            metadata: Optional metadata dict to include in the manifest

        Returns:
            Dict with export_id, zip_base64, manifest, and file list
        """
        t0 = time.time()
        export_id = f"{project_name}-{int(t0)}"
        safe_name = project_name.replace(" ", "_").replace("/", "_")

        buf = io.BytesIO()
        file_manifest: List[Dict[str, str]] = []

        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, content in files.items():
                arc_path = f"{safe_name}/{filename}"
                zf.writestr(arc_path, content)
                file_manifest.append({
                    "filename": filename,
                    "arc_path": arc_path,
                    "size_bytes": len(content.encode()),
                    "sha256": self._file_hash(content),
                })

            # Write manifest
            manifest = {
                "export_id": export_id,
                "project_name": project_name,
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "files": file_manifest,
                "metadata": metadata or {},
                "version": self.VERSION,
            }
            zf.writestr(f"{safe_name}/MANIFEST.json", json.dumps(manifest, indent=2))

        zip_bytes = buf.getvalue()
        zip_b64 = base64.b64encode(zip_bytes).decode()

        # Save manifest for later import validation
        self._manifests[export_id] = manifest

        # Persist ZIP to disk
        zip_path = os.path.join(self.export_dir, f"{safe_name}.zip")
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return {
            "export_id": export_id,
            "project_name": project_name,
            "archive_filename": f"{safe_name}.zip",
            "archive_path": zip_path,
            "zip_base64": zip_b64,
            "zip_size_bytes": len(zip_bytes),
            "file_count": len(files),
            "files": file_manifest,
            "manifest": manifest,
            "latency_ms": round(latency, 2),
        }

    def export_metadata(
        self,
        project_name: str,
        files: Dict[str, str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Export project metadata and a file manifest without creating a ZIP.

        Useful for tracking what was exported and verifying integrity later.

        Args:
            project_name: Name of the project
            files: Dict of {filename: content}
            metadata: Optional additional metadata

        Returns:
            Manifest dict with file hashes and project info
        """
        t0 = time.time()
        export_id = f"{project_name}-meta-{int(t0)}"

        file_manifest = [
            {
                "filename": fname,
                "size_bytes": len(content.encode()),
                "sha256": self._file_hash(content),
                "lines": content.count("\n") + 1,
            }
            for fname, content in files.items()
        ]

        manifest = {
            "export_id": export_id,
            "project_name": project_name,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": file_manifest,
            "total_files": len(files),
            "total_size_bytes": sum(f["size_bytes"] for f in file_manifest),
            "total_lines": sum(f["lines"] for f in file_manifest),
            "metadata": metadata or {},
        }
        self._manifests[export_id] = manifest

        latency = (time.time() - t0) * 1000
        self._record(latency)
        return manifest

    def import_project(
        self,
        export_id: str,
        modified_files: Dict[str, str],
        zip_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import a modified project, detecting changes vs. the original export.

        Compares modified files against the original export manifest to identify
        added, modified, and deleted files.

        Args:
            export_id: The export_id from a previous export_as_zip or export_metadata call
            modified_files: Dict of {filename: content} with the modified project files
            zip_base64: Optional base64-encoded ZIP (used if modified_files is not provided)

        Returns:
            Import result with change detection summary and validation status
        """
        t0 = time.time()

        # If ZIP provided, extract files
        if zip_base64 and not modified_files:
            try:
                zip_bytes = base64.b64decode(zip_base64)
                buf = io.BytesIO(zip_bytes)
                with zipfile.ZipFile(buf, "r") as zf:
                    for name in zf.namelist():
                        if name.endswith("MANIFEST.json"):
                            continue
                        # Strip leading project folder
                        parts = name.split("/", 1)
                        filename = parts[1] if len(parts) > 1 else name
                        if filename:
                            modified_files[filename] = zf.read(name).decode("utf-8", errors="replace")
            except Exception as e:
                latency = (time.time() - t0) * 1000
                self._record(latency, success=False)
                return {"error": f"Failed to extract ZIP: {e}", "latency_ms": round(latency, 2)}

        # Get original manifest
        original = self._manifests.get(export_id)
        original_files: Dict[str, str] = {}
        if original:
            original_files = {f["filename"]: f["sha256"] for f in original.get("files", [])}

        # Detect changes
        added: List[str] = []
        modified: List[str] = []
        deleted: List[str] = []
        unchanged: List[str] = []

        for fname, content in modified_files.items():
            new_hash = self._file_hash(content)
            if fname not in original_files:
                added.append(fname)
            elif original_files[fname] != new_hash:
                modified.append(fname)
            else:
                unchanged.append(fname)

        for fname in original_files:
            if fname not in modified_files:
                deleted.append(fname)

        has_changes = bool(added or modified or deleted)
        latency = (time.time() - t0) * 1000
        self._record(latency)

        return {
            "export_id": export_id,
            "import_status": "success",
            "has_changes": has_changes,
            "change_summary": {
                "added": added,
                "modified": modified,
                "deleted": deleted,
                "unchanged": unchanged,
            },
            "total_changes": len(added) + len(modified) + len(deleted),
            "imported_files": list(modified_files.keys()),
            "file_count": len(modified_files),
            "latency_ms": round(latency, 2),
        }

    def get_health_metrics(self) -> Dict[str, Any]:
        avg = self._total_latency_ms / max(self._call_count, 1)
        return {
            "server": self.SERVER_NAME,
            "version": self.VERSION,
            "status": "healthy",
            "export_dir": self.export_dir,
            "cached_manifests": len(self._manifests),
            "total_calls": self._call_count,
            "success_rate": round(self._success_count / max(self._call_count, 1), 4),
            "avg_latency_ms": round(avg, 2),
        }


project_export_server = ProjectExportServer()
