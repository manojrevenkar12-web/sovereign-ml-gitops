-- Sets the Loki tenant from the Kubernetes namespace: sov-<authority> -> <authority>, anything else -> platform.
-- In the compose e2e there is no Kubernetes metadata; records carry "tenant" themselves.
function set_tenant(tag, timestamp, record)
  local ns = record["kubernetes"] and record["kubernetes"]["namespace_name"]
  local tenant = record["tenant"]
  if ns then
    tenant = ns:match("^sov%-(.+)$") or "platform"
  end
  record["sov_tenant"] = tenant or "platform"
  return 2, timestamp, record
end
