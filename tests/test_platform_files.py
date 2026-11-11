"""The deployment files agree with each other and with tenants/*.yaml."""

import re
import subprocess
import sys

import yaml

from sov.config import ROOT, load_tenants
from sov.tenancy.isolation import loki_probes, parse_policy, token_probes, vault_allows, vault_probes
from sov.tenancy.scaffold import vault_policy


def test_generated_tenant_files_are_fresh():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "scaffold.py"), "--check"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()


def test_no_authority_reaches_another():
    names = sorted(load_tenants())
    probes = vault_probes(names) + token_probes(load_tenants()) + loki_probes(names)
    assert all(p.ok for p in probes), [p for p in probes if not p.ok]
    assert any(p.allowed for p in probes)  # the positive controls pass, so the check is not vacuous


def test_vault_globs():
    policy = parse_policy(vault_policy("a"))
    assert vault_allows(policy, "kv/data/tenants/a/s3", "read")
    assert not vault_allows(policy, "kv/data/tenants/ab/s3", "read")
    assert not vault_allows(policy, "kv/data/tenants/b/s3", "read")


def test_pinned_digests_exist_in_artifacts():
    for name, spec in load_tenants().items():
        for key in ("base", "adapter"):
            d = spec["model"][key]
            if d is None:
                continue
            assert re.fullmatch(r"sha256:[0-9a-f]{64}", d), (name, key)
            assert (ROOT / "artifacts" / f"{d.split(':')[1]}.npz").exists(), (name, key)


def test_applicationset_reads_every_field_it_templates():
    appset = yaml.safe_load((ROOT / "deploy" / "argocd" / "applicationset.yaml").read_text())
    text = yaml.safe_dump(appset["spec"]["template"])
    spec = next(iter(load_tenants().values()))
    for ref in re.findall(r"\{\{\s*\.([\w.]+)\s*\}\}", text):
        node = spec
        for part in ref.split("."):
            assert part in node, f"{ref} missing in tenants/*.yaml"
            node = node[part]


def test_gitlab_pipeline_stages_and_scripts():
    ci = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text())
    stages = ci["stages"]
    for name, job in ci.items():
        if isinstance(job, dict) and "stage" in job:
            assert job["stage"] in stages, name
            for line in job.get("script", []):
                for script in re.findall(r"scripts/[\w_]+\.(?:py|sh)", line):
                    assert (ROOT / script).exists(), (name, script)
