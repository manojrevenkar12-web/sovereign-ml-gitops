"""Static proof that no authority can reach another's secrets, tokens, logs or pods.

Every probe is "can A do X to B?" for every ordered pair, plus the positive control "can A do X to A?",
so a check that denies everything fails too. The same probes run against live Vault, Keycloak and Loki in
CI (tests/e2e).
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from sov.tenancy.scaffold import GENERATED, keycloak_realm, vault_policy

POLICY = re.compile(r'path\s+"([^"]+)"\s*\{\s*capabilities\s*=\s*\[([^\]]*)\]\s*\}', re.S)


@dataclass
class Probe:
    layer: str
    actor: str
    target: str
    action: str
    allowed: bool
    expected: bool

    @property
    def ok(self) -> bool:
        return self.allowed == self.expected


def parse_policy(text: str) -> list[tuple[str, set[str]]]:
    out = []
    for path, caps in POLICY.findall(text):
        out.append((path, {c.strip().strip('"') for c in caps.split(",") if c.strip()}))
    return out


def _vault_match(glob: str, path: str) -> bool:
    """Vault path globs: a trailing * matches any suffix; + matches exactly one segment."""
    if "+" in glob:
        pattern = "^" + re.escape(glob).replace(r"\+", "[^/]+").replace(r"\*", ".*") + "$"
        return re.match(pattern, path) is not None
    if glob.endswith("*"):
        return path.startswith(glob[:-1])
    return glob == path


def vault_allows(policy: list[tuple[str, set[str]]], path: str, cap: str) -> bool:
    return any(_vault_match(g, path) and cap in caps for g, caps in policy)


def vault_probes(tenants: list[str]) -> list[Probe]:
    probes = []
    for a in tenants:
        policy = parse_policy(vault_policy(a))
        for b in tenants:
            for action, path, cap in (
                ("read s3 credentials", f"kv/data/tenants/{b}/s3", "read"),
                ("list secrets", f"kv/metadata/tenants/{b}/", "list"),
                ("write secrets", f"kv/data/tenants/{b}/s3", "update"),
            ):
                expected = a == b and cap != "update"
                probes.append(Probe("vault", a, b, action, vault_allows(policy, path, cap), expected))
    return probes


def token_probes(specs: dict[str, dict[str, Any]], keycloak_url: str = "https://id.sov.example") -> list[Probe]:
    """A token is accepted by B's router only if its issuer is B's realm (the router checks iss first)."""
    probes = []
    for a, spec_a in specs.items():
        issuer = f"{keycloak_url}/realms/{keycloak_realm(spec_a)['realm']}"
        for b in specs:
            accepted_issuer = f"{keycloak_url}/realms/{b}"
            probes.append(Probe("keycloak", a, b, "call the router with a token", issuer == accepted_issuer, a == b))
    return probes


def loki_probes(tenants: list[str]) -> list[Probe]:
    """Each Grafana data source sends exactly one X-Scope-OrgID; Loki returns only that tenant's streams."""
    ds = yaml.safe_load((GENERATED / "grafana" / "datasources.yaml").read_text(encoding="utf-8"))["datasources"]
    probes = []
    for a in tenants:
        mine = [d for d in ds if d["uid"] == f"loki-{a}"]
        org = mine[0]["secureJsonData"]["httpHeaderValue1"] if mine else None
        for b in tenants:
            probes.append(Probe("loki", a, b, "read logs through Grafana", org == b, a == b))
    return probes


def _selects_namespace(peer: dict[str, Any], ns: str) -> bool:
    if "ipBlock" in peer:
        return True  # an IP range may contain another namespace's pods
    sel = peer.get("namespaceSelector")
    if sel is None:
        return False  # a bare podSelector only selects pods in the policy's own namespace
    labels = sel.get("matchLabels", {})
    if not labels and not sel.get("matchExpressions"):
        return True  # {} selects every namespace
    name = labels.get("kubernetes.io/metadata.name")
    tenant = labels.get("sov/tenant")
    if name is not None:
        return fnmatch.fnmatch(ns, name)
    if tenant is not None:
        return ns == f"sov-{tenant}"
    return True  # conservative: an unknown selector might select it


def network_probes(rendered: dict[str, list[dict[str, Any]]]) -> list[Probe]:
    """rendered: tenant -> the chart's manifests for that tenant (helm template output)."""
    probes = []
    tenants = sorted(rendered)
    for b in tenants:
        pols = [d for d in rendered[b] if d and d.get("kind") == "NetworkPolicy"]
        default_deny = any(
            p["spec"].get("podSelector") == {}
            and not p["spec"].get("ingress")
            and "Ingress" in p["spec"].get("policyTypes", [])
            for p in pols
        )
        for a in tenants:
            if a == b:
                continue
            reachable = not default_deny or any(
                _selects_namespace(peer, f"sov-{a}")
                for p in pols
                for rule in p["spec"].get("ingress", []) or []
                for peer in rule.get("from", [])
            )
            probes.append(Probe("network", a, b, "open a connection to the router pods", reachable, False))
    return probes


def load_rendered(directory: Path) -> dict[str, list[dict[str, Any]]]:
    out = {}
    for path in sorted(directory.glob("*.yaml")):
        out[path.stem] = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    return out


def summary(probes: list[Probe]) -> dict[str, Any]:
    by_layer: dict[str, dict[str, int]] = {}
    for p in probes:
        layer = by_layer.setdefault(p.layer, {"cross_tenant": 0, "cross_tenant_allowed": 0, "own": 0, "own_allowed": 0})
        if p.actor == p.target:
            if p.expected:  # the controls: what an authority must be able to do to itself
                layer["own"] += 1
                layer["own_allowed"] += p.allowed
        else:
            layer["cross_tenant"] += 1
            layer["cross_tenant_allowed"] += p.allowed
    return {
        "ok": all(p.ok for p in probes),
        "by_layer": by_layer,
        "failures": [asdict(p) for p in probes if not p.ok],
        "probes": json.loads(json.dumps([asdict(p) for p in probes])),
    }
