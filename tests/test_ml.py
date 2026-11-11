import numpy as np
import pytest

from sov.ml import train
from sov.ml.gate import decide, paired_lower_bound
from sov.ml.pipeline import ContractError, Export, contract, data_digest, residual_per_1k
from sov.ml.registry import IntegrityError, Registry, pack
from sov.serve.infer import NumpyRouter
from sov.world.inquiries import generate, generic_corpus, routing


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    import sov.config as C

    cfg = C.platform()["train"]
    saved = (cfg["base"]["epochs"], cfg["adapter"]["epochs"])
    cfg["base"]["epochs"], cfg["adapter"]["epochs"] = 2, 4
    corpus = generic_corpus(600, 1)
    base = train.train_base([q.text for q in corpus], [q.handler_label for q in corpus])
    tenant = generate("kreis-lindenau", 300, 1)
    adapter = train.train_adapter(base, [q.text for q in tenant], [q.handler_label for q in tenant], ["ordnungsamt"])
    yield base, adapter
    cfg["base"]["epochs"], cfg["adapter"]["epochs"] = saved


def test_numpy_serving_matches_torch_training(small):
    base, adapter = small
    texts = [q.text for q in generate("kreis-lindenau", 50, 9)]
    torch_p = train.Predictor(base, adapter).proba(texts)
    numpy_p = NumpyRouter(base, adapter).proba(texts)
    assert np.allclose(torch_p, numpy_p, atol=1e-4)


def test_a_fresh_adapter_changes_nothing(small):
    base, _ = small
    texts = ["sperrmüll abholung anmelden", "auto zulassen"]
    zero = {k: v.detach().numpy() for k, v in train.new_adapter().state_dict().items()}
    assert np.allclose(train.Predictor(base).proba(texts), train.Predictor(base, zero).proba(texts), atol=1e-6)


def test_registry_refuses_tampered_bytes(small, tmp_path):
    base, _ = small
    reg = Registry(tmp_path)
    digest = reg.put(base, {"kind": "base"})
    assert pack(base) == pack(base)  # reproducible bytes, so reproducible digests
    path = tmp_path / f"{digest.split(':')[1]}.npz"
    data = bytearray(path.read_bytes())
    data[-10] ^= 1
    path.write_bytes(bytes(data))
    with pytest.raises(IntegrityError):
        reg.get(digest)
    with pytest.raises(IntegrityError):
        reg.get("sha256:../../etc/passwd")


def test_contract_needs_critical_examples():
    export = Export("kreis-lindenau", ["x"] * 200, ["extern"] * 200)
    with pytest.raises(ContractError, match="ordnungsamt: 0 of 30"):
        contract(export, ["ordnungsamt"])
    with pytest.raises(ContractError, match="outside"):
        contract(Export("x", ["a"] * 200, ["nope"] * 200))


def test_gate_blocks_personal_data_and_regressions():
    labels = ["kfz"] * 300 + ["ordnungsamt"] * 100
    good = list(labels)
    ok = decide(good, good, labels, ["ordnungsamt"], 0.0, 1.0, 500)
    assert ok.promote
    leaky = decide(good, good, labels, ["ordnungsamt"], 12.0, 1.0, 500)
    assert not leaky.promote and "personal-data" in leaky.summary()
    worse = ["kfz"] * 400
    held = decide(worse, good, labels, ["ordnungsamt"], 0.0, 1.0, 500)
    assert not held.promote and "recall" in held.summary()


def test_paired_bound_is_negative_when_candidate_loses():
    rng = np.random.default_rng(0)
    champ = rng.random(1000) < 0.95
    cand = champ & (rng.random(1000) < 0.95)
    assert paired_lower_bound(cand, champ, 500, 0.95) < -3


def test_residual_and_data_digest():
    assert residual_per_1k(["mein name ist Anna Schmidt", "kein name"]) == 500.0
    assert data_digest(["a"], ["kfz"]) != data_digest(["a"], ["extern"])


def test_world_routing_differs_by_authority():
    assert routing("stadt-nordhafen")["sperrmuell"] == "extern"
    assert routing("kreis-lindenau")["ummeldung"] == "extern"
    assert routing("stadt-nordhafen", after_reorg=False)["bewohnerparken"] == "kfz"
