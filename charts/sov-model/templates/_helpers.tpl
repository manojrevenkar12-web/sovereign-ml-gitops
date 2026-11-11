{{- define "sov.tenant" -}}
{{- required "tenant is required" .Values.tenant -}}
{{- end -}}

{{- define "sov.name" -}}
sov-model
{{- end -}}

{{- define "sov.labels" -}}
app.kubernetes.io/name: sov-model
app.kubernetes.io/instance: {{ include "sov.tenant" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
sov/tenant: {{ include "sov.tenant" . }}
{{- end -}}

{{- define "sov.selector" -}}
app.kubernetes.io/name: sov-model
app.kubernetes.io/instance: {{ include "sov.tenant" . }}
{{- end -}}

{{- define "sov.digest" -}}
{{- $d := . | toString -}}
{{- if not (regexMatch "^sha256:[0-9a-f]{64}$" $d) -}}
{{- fail (printf "model digests must be sha256:<64 hex>, got %q" $d) -}}
{{- end -}}
{{- $d -}}
{{- end -}}

{{/* Live when an adapter digest is pinned. Argo CD renders a YAML null as "<no value>" or "<nil>". */}}
{{- define "sov.live" -}}
{{- $a := toString .Values.model.adapter -}}
{{- if not (has $a (list "" "null" "<nil>" "<no value>")) -}}true{{- end -}}
{{- end -}}
