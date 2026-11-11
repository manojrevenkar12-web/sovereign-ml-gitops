"""Live isolation and privacy probes against deploy/compose/e2e.yaml (CI job "e2e services").

Every probe is a real request: a token from one authority's Keycloak realm against another authority's
router, a Vault token with one authority's policy against another's secrets, and a log line with
personal data through Fluent Bit into Loki, read back under each tenant id.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.e2e

KC = os.environ.get("E2E_KEYCLOAK", "http://localhost:8080")
VAULT = os.environ.get("E2E_VAULT", "http://localhost:8200")
LOKI = os.environ.get("E2E_LOKI", "http://localhost:3100")
FLUENT = os.environ.get("E2E_FLUENT", "http://localhost:9880")
API = {"stadt-nordhafen": "http://localhost:8081", "stadt-weidenbach": "http://localhost:8082"}
TAMPERED = "http://localhost:8083"
LIVE = list(API)
ALL = ["stadt-nordhafen", "stadt-weidenbach", "kreis-lindenau"]
RESULTS: list[dict] = []


def record(layer: str, actor: str, target: str, allowed: bool, expected: bool) -> None:
    RESULTS.append({"layer": layer, "actor": actor, "target": target, "allowed": allowed, "expected": expected})
    out = Path(os.environ.get("E2E_REPORT", "build/e2e.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(RESULTS, indent=2))


def wait(url: str, ok=(200,), timeout=180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=3).status_code in ok:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise TimeoutError(url)


@pytest.fixture(scope="session")
def admin() -> httpx.Client:
    wait(f"{KC}/realms/master")
    tok = httpx.post(
        f"{KC}/realms/master/protocol/openid-connect/token",
        data={"grant_type": "password", "client_id": "admin-cli", "username": "admin", "password": "admin"},
    ).json()["access_token"]
    return httpx.Client(base_url=f"{KC}/admin/realms", headers={"Authorization": f"Bearer {tok}"}, timeout=20)


def _client(admin: httpx.Client, realm: str, client_id: str, audience: bool) -> str:
    body = {
        "clientId": client_id,
        "enabled": True,
        "publicClient": False,
        "directAccessGrantsEnabled": True,
        "standardFlowEnabled": False,
        "serviceAccountsEnabled": False,
    }
    if audience:
        body["protocolMappers"] = [
            {
                "name": "audience",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "config": {"included.client.audience": "inquiry-router-api", "access.token.claim": "true"},
            }
        ]
    admin.post(f"/{realm}/clients", json=body)
    cid = admin.get(f"/{realm}/clients", params={"clientId": client_id}).json()[0]["id"]
    return admin.get(f"/{realm}/clients/{cid}/client-secret").json()["value"]


def _user(admin: httpx.Client, realm: str, username: str, groups: list[str]) -> None:
    admin.post(
        f"/{realm}/users",
        json={
            "username": username,
            "enabled": True,
            "email": f"{username}@{realm}.example",
            "emailVerified": True,
            "firstName": "Test",
            "lastName": "User",
            "groups": groups,
            "credentials": [{"type": "password", "value": "e2e-Passw0rd!", "temporary": False}],
        },
    )


@pytest.fixture(scope="session")
def tokens(admin: httpx.Client) -> dict[tuple[str, str, str], str]:
    out = {}
    for realm in LIVE:
        secrets = {
            "e2e-tester": _client(admin, realm, "e2e-tester", True),
            "e2e-no-aud": _client(admin, realm, "e2e-no-aud", False),
        }
        _user(admin, realm, "clerk", ["/buergerservice"])
        _user(admin, realm, "visitor", [])
        for user in ("clerk", "visitor"):
            for client, secret in secrets.items():
                r = httpx.post(
                    f"{KC}/realms/{realm}/protocol/openid-connect/token",
                    data={
                        "grant_type": "password",
                        "client_id": client,
                        "client_secret": secret,
                        "username": user,
                        "password": "e2e-Passw0rd!",
                        "scope": "openid",
                    },
                )
                assert r.status_code == 200, r.text
                out[(realm, user, client)] = r.json()["access_token"]
    return out


def route(base: str, tenant: str, token: str) -> httpx.Response:
    return httpx.post(
        f"{base}/v1/tenants/{tenant}/route",
        json={"text": "sperrmüll abholung anmelden"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )


def test_routers_are_ready_with_pinned_digests():
    for base in API.values():
        wait(f"{base}/readyz")


def test_tokens_only_work_at_their_own_authority(tokens):
    for actor in LIVE:
        for target in LIVE:
            r = route(API[target], target, tokens[(actor, "clerk", "e2e-tester")])
            record("keycloak", actor, target, r.status_code == 200, actor == target)
            if actor == target:
                assert r.status_code == 200, r.text
                assert r.json()["department"]
            else:
                assert (r.status_code, r.json()["detail"]) == (401, "issuer")


def test_role_and_audience_are_enforced(tokens):
    for t in LIVE:
        r = route(API[t], t, tokens[(t, "visitor", "e2e-tester")])
        assert (r.status_code, r.json()["detail"]) == (403, "role")
        r = route(API[t], t, tokens[(t, "clerk", "e2e-no-aud")])
        assert (r.status_code, r.json()["detail"]) == (401, "audience")


def test_a_tampered_artifact_is_never_served():
    wait(f"{TAMPERED}/healthz")
    r = httpx.get(f"{TAMPERED}/readyz")
    assert r.status_code == 503
    assert "does not hash to" in r.json()["reason"]


def test_vault_policies_from_the_scaffold_hold():
    root = {"X-Vault-Token": "e2e-root"}
    wait(f"{VAULT}/v1/sys/health")
    httpx.post(f"{VAULT}/v1/sys/mounts/kv", headers=root, json={"type": "kv", "options": {"version": "2"}})
    generated = Path(__file__).resolve().parents[2] / "deploy" / "generated" / "vault"
    tokens = {}
    for t in ALL:
        r = httpx.post(
            f"{VAULT}/v1/kv/data/tenants/{t}/s3",
            headers=root,
            json={"data": {"access_key": f"ak-{t}", "secret_key": uuid.uuid4().hex}},
        )
        assert r.status_code == 200, r.text
        r = httpx.put(
            f"{VAULT}/v1/sys/policies/acl/sov-{t}", headers=root, json={"policy": (generated / f"{t}.hcl").read_text()}
        )
        assert r.status_code == 204, r.text
        tokens[t] = httpx.post(
            f"{VAULT}/v1/auth/token/create", headers=root, json={"policies": [f"sov-{t}"], "ttl": "10m"}
        ).json()["auth"]["client_token"]
    for a in ALL:
        for b in ALL:
            r = httpx.get(f"{VAULT}/v1/kv/data/tenants/{b}/s3", headers={"X-Vault-Token": tokens[a]})
            record("vault", a, b, r.status_code == 200, a == b)
            assert r.status_code == (200 if a == b else 403), (a, b, r.text)
            w = httpx.post(
                f"{VAULT}/v1/kv/data/tenants/{b}/s3",
                headers={"X-Vault-Token": tokens[a]},
                json={"data": {"access_key": "x"}},
            )
            assert w.status_code == 403, (a, b, "write")


def test_personal_data_never_reaches_loki_and_tenants_stay_apart():
    wait(f"{LOKI}/ready", timeout=120)
    marker = uuid.uuid4().hex[:12]
    lines = {
        "stadt-nordhafen": f"{marker} validation failed body=mein name ist Anna Schmidt, iban DE89 3704 0044 0532 0130 00",
        "stadt-weidenbach": f"{marker} rückruf bitte unter 0151 23456789, steuer-id 86095742719",
    }
    for tenant, log in lines.items():
        deadline = time.time() + 60
        while True:
            try:
                r = httpx.post(f"{FLUENT}/", json={"tenant": tenant, "log": log}, timeout=5)
                if r.status_code < 300:
                    break
            except httpx.HTTPError:
                pass
            assert time.time() < deadline, "fluent-bit http input not reachable"
            time.sleep(2)

    def query(org: str) -> list[str]:
        r = httpx.get(
            f"{LOKI}/loki/api/v1/query_range",
            headers={"X-Scope-OrgID": org},
            params={
                "query": f'{{job="e2e"}} |= "{marker}"',
                "limit": 100,
                "start": str(int((time.time() - 600) * 1e9)),
                "end": str(int((time.time() + 60) * 1e9)),
            },
        )
        r.raise_for_status()
        return [v[1] for s in r.json()["data"]["result"] for v in s["values"]]

    deadline = time.time() + 90
    seen: dict[str, list[str]] = {}
    while time.time() < deadline:
        seen = {t: query(t) for t in ALL}
        if seen["stadt-nordhafen"] and seen["stadt-weidenbach"]:
            break
        time.sleep(3)
    for a in ALL:
        for b in lines:
            visible = any(marker in s and ("<name>" in s or "<phone>" in s) and b in s for s in seen[a])
            record("loki", a, b, visible, a == b)
    nord, weid = seen["stadt-nordhafen"], seen["stadt-weidenbach"]
    if not (nord and weid):
        for org in ALL:
            r = httpx.get(f"{LOKI}/loki/api/v1/labels", headers={"X-Scope-OrgID": org})
            print("labels", org, r.status_code, r.text[:300])
    assert nord and weid, seen
    assert seen["kreis-lindenau"] == []
    for s in nord + weid:
        for secret in ("Anna Schmidt", "3704 0044", "23456789", "86095742719"):
            assert secret not in s
    assert '"pii_redactions":2' in nord[0].replace(" ", "")
    assert all("stadt-weidenbach" not in s for s in nord)
