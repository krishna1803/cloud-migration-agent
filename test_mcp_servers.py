"""Smoke test for all MCP servers and LangChain tools."""
import sys

def test_all():
    # ── Pricing ──────────────────────────────────────────────────────────────
    from src.mcp_servers.pricing_server import pricing_server
    result = pricing_server.oci_estimate([
        {"type": "compute", "name": "App Server", "shape": "VM.Standard.E4.Flex", "ocpu": 2, "memory_gb": 16, "quantity": 2},
        {"type": "database", "name": "ATP", "db_service": "Autonomous Database OLTP", "ocpu": 2, "storage_tb": 1},
        {"type": "storage", "name": "Object Store", "storage_class": "Object Storage Standard", "size_gb": 500},
        {"type": "load_balancer", "name": "LB", "lb_type": "flexible", "quantity": 1},
    ])
    print("=== PRICING ===")
    print(f"  Total monthly: ${result['total_monthly_cost_usd']:.2f}")
    print(f"  Total annual:  ${result['total_annual_cost_usd']:.2f}")
    for li in result["line_items"]:
        print(f"  {li['name']}: ${li['monthly_cost_usd']:.2f}/mo")

    compute_est = pricing_server.estimate_compute("VM.Standard.E4.Flex", 4, 64)
    print(f"  E4.Flex 4OCPU/64GB: ${compute_est['monthly_cost_usd']:.2f}/mo")

    db_est = pricing_server.estimate_database("Autonomous Database OLTP", 2, 1.0)
    print(f"  ATP 2OCPU/1TB: ${db_est['monthly_cost_usd']:.2f}/mo")

    savings = pricing_server.compare_with_source(5000, 3200, 10000)
    print(f"  Savings: {savings['savings_percentage']}%, payback: {savings['payback_months']} months")

    # ── Sizing ────────────────────────────────────────────────────────────────
    from src.mcp_servers.sizing_server import sizing_server
    print("\n=== SIZING ===")
    r = sizing_server.estimate_compute("m5.xlarge", "AWS", "general")
    print(f"  AWS m5.xlarge -> {r['recommended_shape']}, {r['ocpu']} OCPU, {r['memory_gb']} GB, ${r['oci_monthly_cost_usd']}/mo")
    print(f"    Source cost: ${r['source_monthly_cost_usd']}, savings: {r['estimated_savings_pct']}%")

    az = sizing_server.estimate_compute("Standard_D8s_v3", "Azure", "general")
    print(f"  Azure D8s_v3 -> {az['recommended_shape']}, ${az['oci_monthly_cost_usd']}/mo")

    gcp = sizing_server.estimate_compute("n2-standard-8", "GCP", "general")
    print(f"  GCP n2-standard-8 -> {gcp['recommended_shape']}, ${gcp['oci_monthly_cost_usd']}/mo")

    arm = sizing_server.recommend_shape("microservices", prefer_arm=True)
    print(f"  ARM recommendation: {arm['primary']['shape']} @ ${arm['primary']['monthly_cost_usd']}/mo")

    s = sizing_server.estimate_storage("ebs", 500, iops=3000)
    print(f"  EBS 500GB/3000IOPS -> {s['oci_service']}, ${s['monthly_cost_usd']}/mo, VPU: {s['recommended_vpu']}")

    # ── Mapping ───────────────────────────────────────────────────────────────
    from src.mcp_servers.mapping_server import mapping_server
    print("\n=== MAPPING ===")
    aws_svcs = ["EC2", "S3", "RDS", "LAMBDA", "DYNAMODB", "VPC", "ELB", "CLOUDWATCH", "KMS", "EKS", "SNS", "SQS"]
    m = mapping_server.bulk_map(aws_svcs, "AWS")
    print(f"  AWS: {m['auto_mapped']}/{m['total']} mapped (avg conf: {m['avg_confidence']})")

    azure = mapping_server.bulk_map(["Virtual Machine", "Blob Storage", "Azure SQL", "AKS", "Key Vault"], "Azure")
    print(f"  Azure: {azure['auto_mapped']}/{azure['total']} mapped")

    gcp2 = mapping_server.bulk_map(["Compute Engine", "Cloud Storage", "BigQuery", "GKE", "Pub/Sub", "Cloud SQL"], "GCP")
    print(f"  GCP: {gcp2['auto_mapped']}/{gcp2['total']} mapped")

    single = mapping_server.map_service("CLOUDFORMATION", "AWS")
    print(f"  CloudFormation -> {single['oci_service']} (conf: {single['confidence']})")

    # ── RefArch ───────────────────────────────────────────────────────────────
    from src.mcp_servers.refarch_server import refarch_server
    print("\n=== REFARCH ===")
    r2 = refarch_server.match_pattern(
        "three tier web application with load balancer compute and autonomous database",
        services=["Load Balancer", "Compute", "Database"],
        source_provider="AWS",
    )
    best = r2["best_match"]
    print(f"  Best: {best['name']} (score: {best['match_score']}, ${best.get('estimated_monthly_cost_usd')}/mo)")
    print(f"  Components: {best['components'][:3]}")
    if r2["alternatives"]:
        print(f"  Alt: {r2['alternatives'][0]['name']} (score: {r2['alternatives'][0]['match_score']})")

    cats = refarch_server.get_categories()
    print(f"  Categories: {list(cats['categories'].keys())}")

    k8s = refarch_server.match_pattern("kubernetes microservices eks containers", source_provider="AWS")
    print(f"  K8s: {k8s['best_match']['name']}")

    # ── OCI RM ────────────────────────────────────────────────────────────────
    from src.mcp_servers.oci_rm_server import oci_rm_server
    print("\n=== OCI RESOURCE MANAGER ===")
    h = oci_rm_server.get_health_metrics()
    print(f"  Mode: {h['mode']}, SDK: {h['sdk_available']}")

    stk = oci_rm_server.create_stack(
        "test-migration-stack",
        'resource "oci_core_vcn" "main" { compartment_id = var.compartment_ocid cidr_blocks = ["10.0.0.0/16"] }',
        "ocid1.compartment.oc1..testcompartment",
    )
    sid = stk["stack_id"]
    print(f"  Stack created: {sid[:40]}...")

    plan = oci_rm_server.plan_stack(sid)
    jid = plan["job_id"]
    print(f"  Plan job: {jid[:40]}...")
    print(f"  Plan output preview: {plan.get('plan_output', '')[:80]}...")

    job = oci_rm_server.get_job(jid)
    print(f"  Job status: {job['job']['lifecycle_state']}")

    logs = oci_rm_server.get_job_logs(jid)
    print(f"  Log entries: {logs['log_count']}, first: {logs['logs'][0]['message'][:50]}")

    # ── Terraform Gen ─────────────────────────────────────────────────────────
    from src.mcp_servers.terraform_gen_server import terraform_gen_server
    print("\n=== TERRAFORM GEN ===")
    proj = terraform_gen_server.generate_three_tier_project("my-migration", "us-ashburn-1")
    print(f"  Files: {list(proj['files'].keys())}")
    for fname, content in proj["files"].items():
        print(f"    {fname}: {len(content)} chars")

    vcn = terraform_gen_server.generate_resource("oci_core_vcn", "main_vcn", {"cidr_block": "10.0.0.0/16"})
    print(f"  VCN resource: template_found={vcn['template_found']}, {len(vcn['content'])} chars")

    inst = terraform_gen_server.generate_resource("oci_core_instance", "app_server", {"shape": "VM.Standard.E4.Flex", "ocpu": 4, "memory_gb": 64, "subnet_ref": "app", "nsg_ref": "app_nsg"})
    print(f"  Instance resource: template_found={inst['template_found']}")

    shapes = terraform_gen_server.list_resource_types()
    print(f"  Supported resources: {shapes['count']}")

    # ── LangChain Tools ───────────────────────────────────────────────────────
    from src.tools import get_all_tools
    tools = get_all_tools()
    print(f"\n=== LANGCHAIN TOOLS ({len(tools)}) ===")
    for t in tools:
        print(f"  - {t.name}")

    # Run one tool end-to-end
    mapping_tool = next(t for t in tools if t.name == "oci_service_mapping")
    tool_result = mapping_tool._run(["EC2", "S3", "RDS", "EKS"], "AWS")
    import json
    parsed = json.loads(tool_result)
    print(f"  Tool test (mapping): {parsed['auto_mapped']}/{parsed['total']} auto-mapped")

    pricing_tool = next(t for t in tools if t.name == "oci_pricing_estimation")
    pr = json.loads(pricing_tool._run([
        {"type": "compute", "name": "web", "shape": "VM.Standard.E4.Flex", "ocpu": 2, "memory_gb": 16},
        {"type": "database", "name": "db", "db_service": "Autonomous Database OLTP", "ocpu": 2, "storage_tb": 1},
    ]))
    print(f"  Tool test (pricing): ${pr['total_monthly_cost_usd']:.2f}/mo")

    print("\n✓ All MCP servers and LangChain tools verified successfully!")


if __name__ == "__main__":
    test_all()
