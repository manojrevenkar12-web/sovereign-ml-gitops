# Runbook

Alerts carry `runbook_url` links to the sections below. Every action goes through git unless it says
otherwise.

## Slow routing

`SovRouterSlow`: the 95th percentile of routing time is above 25 ms for 15 minutes.

1. In Grafana, open "Loki <authority>" and filter `event="routed"` by `latency_ms`. Find out whether one pod
   or all pods are slow.
2. One pod: check the node with `kubectl describe pod`, delete the pod, and let the Deployment replace it.
3. All pods: check whether a release just merged (`sov/adapter` annotation, Argo CD history). If it did,
   revert the merge request. Argo CD rolls back.

## Handoff share

`SovHandoffShareUp`: more than 15% of inquiries fall below the confidence threshold and go to a person.

This usually means the citizens' wording changed: a new local service, a new pass, a reorganisation.

1. Ask the authority's contact (`contact` in `tenants/<name>.yaml`) what changed.
2. Schedule a fine-tune on a fresh export (GitLab schedule, `TENANT=<name>`).
3. The gate decides whether the new adapter ships.

## Auth failures

`SovAuthFailuresUp`: the router refuses tokens.

The `reason` label says why:

- **issuer:** a client is configured with another authority's realm. Fix the client; the router is right.
- **audience:** the client lacks the audience mapper. Fix it through `infra/platform`, not in the admin
  console.
- **role:** a user is missing the group.
- **expired:** check the clock on the client.

## Artifact integrity

`SovArtifactIntegrity` (critical): an artifact did not hash to the digest pinned in git. The pod stays
unready and serves nothing.

1. Do not "fix" the digest. Find out why the bytes differ: bucket versioning shows who wrote the object and
   when.
2. Restore the object version that matches the digest, then delete the pod.
3. If the object was overwritten on purpose, that was a release outside git. Raise it as a security
   incident.

## Personal data in a service's logs

The `pii_redactions` field in Loki counts how many values the filter replaced in a line.
`sum by (container) (count_over_time({job="fluent-bit"} | json | pii_redactions > 0 [1h]))` names the
container that is logging personal data.

The filter has already removed the values, but the service must stop logging them. Open an issue with the
owning team.
