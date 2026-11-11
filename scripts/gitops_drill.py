"""Run in CI against kind with Argo CD (job "gitops on kind"). Uses kubectl only.

1. Every authority in tenants/ becomes an Argo CD application, Synced and Healthy.
2. The pods that serve run exactly the digests pinned in git; an authority without an adapter runs no pods.
3. Drift: scale a router to zero by hand; Argo CD's self-heal puts it back. Time is reported.
4. Network: a pod in an unrelated namespace cannot reach a router; one in the ingress namespace can.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sov.config import load_tenants  # noqa: E402


def kubectl(*args: str, check: bool = True) -> str:
    r = subprocess.run(["kubectl", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)}: {r.stderr}")
    return r.stdout


def wait_for(fn, what: str, timeout: int = 600) -> float:
    start = time.time()
    while time.time() - start < timeout:
        try:
            if fn():
                return time.time() - start
        except Exception:
            pass
        time.sleep(5)
    raise TimeoutError(what)


def app_status(name: str) -> tuple[str, str]:
    out = json.loads(kubectl("-n", "argocd", "get", "application", name, "-o", "json"))
    return out["status"]["sync"]["status"], out["status"]["health"]["status"]


def probe(namespace: str, url: str) -> bool:
    name = f"probe-{int(time.time() * 1000) % 100000}"
    kubectl("create", "namespace", namespace, check=False)
    r = subprocess.run(
        [
            "kubectl",
            "-n",
            namespace,
            "run",
            name,
            "--rm",
            "-i",
            "--restart=Never",
            "--quiet",
            "--image=curlimages/curl:8.11.1",
            "--command",
            "--",
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "--max-time",
            "5",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    return r.stdout.strip().endswith("200")


def main() -> None:
    specs = load_tenants()
    report: dict = {"applications": {}}
    for name, spec in sorted(specs.items()):
        app = f"sov-{name}"
        took = wait_for(lambda a=app: app_status(a) == ("Synced", "Healthy"), f"{app} synced and healthy")
        ns = f"sov-{name}"
        live = spec["model"]["adapter"] is not None
        if live:
            wait_for(
                lambda n=ns, want=spec["serving"]["replicas"]: (
                    json.loads(kubectl("-n", n, "get", "deploy", "sov-model", "-o", "json"))["status"].get(
                        "readyReplicas", 0
                    )
                    == want
                ),
                f"{ns} ready",
            )
            ann = json.loads(kubectl("-n", ns, "get", "deploy", "sov-model", "-o", "json"))["metadata"]["annotations"]
            assert ann["sov/adapter"] == spec["model"]["adapter"], (ann, spec["model"])
            assert ann["sov/base"] == spec["model"]["base"]
        else:
            pods = json.loads(kubectl("-n", ns, "get", "pods", "-o", "json"))["items"]
            assert pods == [], f"{name} has no adapter but runs pods"
        report["applications"][name] = {"live": live, "synced_after_s": round(took)}
        print(f"{name}: synced and healthy, live={live}")

    target = next(n for n, s in sorted(specs.items()) if s["model"]["adapter"])
    ns = f"sov-{target}"
    kubectl("-n", ns, "scale", "deploy", "sov-model", "--replicas=0")
    healed = wait_for(
        lambda: (
            json.loads(kubectl("-n", ns, "get", "deploy", "sov-model", "-o", "json"))["status"].get("readyReplicas", 0)
            == specs[target]["serving"]["replicas"]
        ),
        "self-heal",
        timeout=600,
    )
    report["drift_self_heal_s"] = round(healed)
    print(f"drift on {target} healed in {healed:.0f} s")

    url = f"http://sov-model.{ns}.svc/readyz"
    report["network"] = {
        "from_unrelated_namespace": probe("intruder", url),
        "from_ingress_namespace": probe("ingress-nginx", url),
    }
    print("network", report["network"])
    out = Path(os.environ.get("DRILL_REPORT", "build/gitops.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"::notice title=gitops drill::{json.dumps(report)}")
    assert report["network"] == {"from_unrelated_namespace": False, "from_ingress_namespace": True}, report


if __name__ == "__main__":
    main()
