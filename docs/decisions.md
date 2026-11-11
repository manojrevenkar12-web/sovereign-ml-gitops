# Decisions

Each entry: what was decided, what was rejected, and why.

**One Helm chart and an ApplicationSet over `tenants/*.yaml`, not a chart per authority.** Authorities differ
in data, not in what runs. A chart per authority drifts. One file per authority keeps onboarding and release
reviewable in one diff.

**LoRA adapters on a shared base, not a full fine-tune per authority.** The full fine-tune is 1.4 points
more accurate. Per authority, it costs 12× the storage, 4× the training time and a full model in every
router's memory. At hundreds of municipalities the adapter is the only option that fits one cluster, and the
gate measures what the 1.4 points cost.

**Fine-tuning may burst to IONOS Cloud only for pseudonymised data.** Serving stays on the authorities'
premises. `fine_tune.where` in the tenant file records the choice, and the gate's pseudonymisation check is
what makes that choice safe.

**One definition of personal data, compiled to Lua.** The same `redact.lua` runs in Fluent Bit and, through
lupa, in the training pipeline. Two implementations would disagree. With one, a rule added for the logs also
protects the training data. The cost is Lua patterns (no alternation), which is why checksums carry much of
the precision (IBAN mod 97, tax id ISO 7064).

**A first-name list, not an NER model, for names.** It needs no GPU, runs in Fluent Bit, and its misses are
predictable: names not on the list, surname-first rows. An NER model is the next step once the
merge-request format check exists to measure it ([heldout.md](heldout.md)).

**A release gate with a paired bootstrap bound and per-department recall floors, not "accuracy within 1
point".** Accuracy alone shipped models trained on raw personal data (their accuracy was fine), and missed
a collapsed hazard-report department (overall accuracy hid it). The bound holds some good releases. That is
cheap, because the current model keeps serving.

**The contract requires 30 examples of each critical department, topped up from the archive.** Without
that, a district's hazard reports are a handful per export and recall cannot even be measured. Top-up
selects by the case handler's label, as a real archive query would.

**Lindenau stays held.** Weighting the critical class 4× in the loss raised hazard recall from 60% to 63%.
Weighting 10× or 20× reached 67%. None reached the 85% floor. Lowering the floor would make the gate
decorative.

**Artifacts are `.npz` with fixed member order and timestamps, never pickles.** Equal weights give equal
bytes, so equal digests, so a re-run reproduces the digest pinned in git. Loading runs with
`allow_pickle=False`.

**The serving image has no torch.** Inference is a 30-line numpy forward pass, tested equal to the torch
model. The image is a slim Python with numpy and FastAPI; torch's CPU wheel alone would add several hundred MB.
That matters on air-gapped sites, where every image is mirrored by hand.

**Deployments are pull-based.** No pipeline holds production cluster credentials. GitLab opens a merge
request, and Argo CD applies what is merged. A sync window keeps automatic rollouts out of the authorities'
morning peak.

**One Keycloak realm per authority, not one realm with a tenant claim.** A tenant claim is one mapper
misconfiguration away from crossing authorities. Separate realms give separate issuers, and the router checks
the issuer before anything else.

**Fluent Bit re-tags every record by authority before the Loki output.** Found by the live probe on the first
CI run: the Loki output takes `tenant_id_key` from a chunk, not from each record. On a node, chunks follow
container log files and so belong to one namespace. Any input that mixes authorities (an HTTP or forward
input, a shared sidecar) would put one authority's lines into another's tenant. `rewrite_tag` makes the
tenant part of the tag, so a chunk can only hold one authority. The static isolation probes could not see
this, because the configuration was correct on paper.
