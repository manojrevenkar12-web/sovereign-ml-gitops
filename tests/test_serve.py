import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from sov.ml import train
from sov.ml.registry import Registry
from sov.serve.app import Settings, create_app
from sov.world.inquiries import generic_corpus

ISSUER = "http://kc.test/realms/stadt-nordhafen"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(iss=ISSUER, aud="inquiry-router-api", roles=("inquiry-router",), exp=300, key=KEY):
    now = int(time.time())
    return jwt.encode(
        {"iss": iss, "aud": aud, "sub": "u1", "iat": now, "exp": now + exp, "realm_access": {"roles": list(roles)}},
        key,
        algorithm="RS256",
    )


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    import sov.config as C

    cfg = C.platform()["train"]["base"]
    saved, cfg["epochs"] = cfg["epochs"], 1
    corpus = generic_corpus(300, 2)
    base = train.train_base([q.text for q in corpus], [q.handler_label for q in corpus])
    cfg["epochs"] = saved
    root = tmp_path_factory.mktemp("models")
    return root, Registry(root).put(base, {"kind": "base"})


def make_client(root, base, adapter=None):
    settings = Settings("stadt-nordhafen", base, adapter, root, ISSUER, "inquiry-router-api", "unused")
    return TestClient(create_app(settings, resolve=lambda _t: KEY.public_key()))


def test_routes_with_a_valid_token_and_logs_no_text(artifacts, capsys):
    client = make_client(*artifacts)
    r = client.post(
        "/v1/tenants/stadt-nordhafen/route",
        json={"text": "mein name ist Anna Schmidt, sperrmüll"},
        headers={"Authorization": f"Bearer {token()}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["base"] == artifacts[1]
    out = capsys.readouterr().out
    assert "Anna" not in out and "sperrmüll" not in out
    assert json.loads(out.strip().splitlines()[-1])["event"] == "routed"


@pytest.mark.parametrize(
    "tok,status,reason",
    [
        (lambda: token(iss="http://kc.test/realms/kreis-lindenau"), 401, "issuer"),
        (lambda: token(aud="account"), 401, "audience"),
        (lambda: token(roles=("audit-reader",)), 403, "role"),
        (lambda: token(exp=-120), 401, "expired"),
        (lambda: token(key=OTHER_KEY), 401, "signature"),
    ],
)
def test_refuses_tokens_that_are_not_for_this_authority(artifacts, tok, status, reason):
    client = make_client(*artifacts)
    r = client.post(
        "/v1/tenants/stadt-nordhafen/route",
        json={"text": "auto zulassen"},
        headers={"Authorization": f"Bearer {tok()}"},
    )
    assert (r.status_code, r.json()["detail"]) == (status, reason)
    assert f'reason="{reason}"' in client.get("/metrics").text


def test_other_authority_path_and_missing_token(artifacts):
    client = make_client(*artifacts)
    assert (
        client.post(
            "/v1/tenants/kreis-lindenau/route", json={"text": "x"}, headers={"Authorization": f"Bearer {token()}"}
        ).status_code
        == 404
    )
    assert client.post("/v1/tenants/stadt-nordhafen/route", json={"text": "x"}).status_code == 401


def test_not_ready_when_an_artifact_does_not_match_its_digest(artifacts):
    root, base = artifacts
    client = make_client(root, base, adapter="sha256:" + "0" * 64)
    r = client.get("/readyz")
    assert r.status_code == 503
    assert "not in the registry" in r.json()["reason"]
    assert "sov_artifact_integrity_failures_total" in client.get("/metrics").text
