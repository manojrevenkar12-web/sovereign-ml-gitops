# One policy per authority, rendered by OpenTofu (infra/platform) and by scripts/scaffold.py from the
# same template. The authority's workloads may read its own secrets and nothing else.
path "kv/data/tenants/stadt-weidenbach/*" {
  capabilities = ["read"]
}

path "kv/metadata/tenants/stadt-weidenbach/*" {
  capabilities = ["list"]
}
