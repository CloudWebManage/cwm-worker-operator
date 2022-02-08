{{- define "deployment" }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cwm-worker-operator-{{ .deploymentName }}
spec:
  replicas: {{ if eq .deploymentName "web-ui" }}{{ .root.Values.operator.webUiReplicas }}{{ else }}1{{ end }}
  revisionHistoryLimit: {{ .root.Values.revisionHistoryLimit }}
  selector:
    matchLabels:
      app: cwm-worker-operator-{{ .deploymentName }}
  strategy:
    type: {{ if eq .deploymentName "web-ui" }}RollingUpdate{{ else }}Recreate{{ end }}
  template:
    metadata:
      labels:
        app: cwm-worker-operator-{{ .deploymentName }}
      {{ if eq .deploymentName "web-ui" }}
      annotations:
        checksum/config: {{ include (print .root.Template.BasePath "/web-ui-nginx-configmap.yaml") . | sha256sum }}
      {{ end }}
    spec:
      {{- if .root.Values.tolerations }}
      tolerations:
{{ toYaml .root.Values.tolerations | indent 6 }}
      {{- end }}
      terminationGracePeriodSeconds: {{ .root.Values.terminationGracePeriodSeconds }}
      enableServiceLinks: false
      serviceAccountName: cwm-worker-operator
      volumes:
      - name: data
        {{ if .root.Values.enableOperatorPvc }}
        persistentVolumeClaim:
          claimName: cwm-worker-operator
        {{ else }}
        emptyDir: {}
        {{ end }}
      - name: config
        configMap:
          name: web-ui-nginx
      containers:
      {{- include "deployment.containers" . | indent 6 }}
{{- end }}