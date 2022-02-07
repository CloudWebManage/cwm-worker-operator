{{- define "deployment.containers" }}
- name: {{ .deploymentName }}
  {{ if eq .deploymentName "debug" }}
  command: ["sleep", "86400"]
  {{ else }}
  args: [{{ .deploymentName | quote }}, "start_daemon"]
  {{ end }}
  image: {{ .root.Values.operator.image }}:{{ .root.Values.operator.tag | default .root.Chart.AppVersion }}
  imagePullPolicy: {{ .root.Values.operator.imagePullPolicy }}
  {{ if eq .deploymentName "disk-usage-updater" }}
  securityContext:
    privileged: true
  {{ end }}
  env:
  {{- include "deployment.container.env" . | indent 8 }}
  volumeMounts:
  - mountPath: "/data"
    name: "data"
  {{ if eq .deploymentName "web-ui" }}
  readinessProbe:
    httpGet:
      port: 8182
    periodSeconds: 1
    timeoutSeconds: 1
    successThreshold: 2
    failureThreshold: 2
  {{ end }}
  resources:
  {{- include "deployment.container.resources" . | indent 2 }}
{{ if eq .deploymentName "web-ui" }}
- name: nginx
  # Pulled on Dec 1, 2021
  image: nginx@sha256:097c3a0913d7e3a5b01b6c685a60c03632fc7a2b50bc8e35bcaa3691d788226e
  volumeMounts:
  - name: data
    mountPath: /data
  - name: config
    mountPath: /etc/nginx/conf.d
  readinessProbe:
    httpGet:
      port: 80
    periodSeconds: 1
    timeoutSeconds: 1
    successThreshold: 2
    failureThreshold: 2
{{ end }}
{{- end }}
