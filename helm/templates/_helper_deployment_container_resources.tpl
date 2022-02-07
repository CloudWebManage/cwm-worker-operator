{{- define "deployment.container.resources" }}
{{ if and (eq .deploymentName "initializer") .root.Values.operator.initializerResources }}
{{ toYaml .root.Values.operator.initializerResources | indent 10 }}
{{ else if and (eq .deploymentName "deployer") .root.Values.operator.deployerResources }}
{{ toYaml .root.Values.operator.deployerResources | indent 10 }}
{{ else if and (eq .deploymentName "waiter") .root.Values.operator.waiterResources }}
{{ toYaml .root.Values.operator.waiterResources | indent 10 }}
{{ else if and (eq .deploymentName "updater") .root.Values.operator.updaterResources }}
{{ toYaml .root.Values.operator.updaterResources | indent 10 }}
{{ else if and (eq .deploymentName "deleter") .root.Values.operator.deleterResources }}
{{ toYaml .root.Values.operator.deleterResources | indent 10 }}
{{ else if and (eq .deploymentName "metrics-updater") .root.Values.operator.metricsUpdaterResources }}
{{ toYaml .root.Values.operator.metricsUpdaterResources | indent 10 }}
{{ else if and (eq .deploymentName "web-ui") .root.Values.operator.webUiResources }}
{{ toYaml .root.Values.operator.webUiResources | indent 10 }}
{{ else if and (eq .deploymentName "disk-usage-updater") .root.Values.operator.diskUsageUpdaterResources }}
{{ toYaml .root.Values.operator.diskUsageUpdaterResources | indent 10 }}
{{ else if and (eq .deploymentName "alerter") .root.Values.operator.AlerterResources }}
{{ toYaml .root.Values.operator.AlerterResources | indent 10 }}
{{ else if and (eq .deploymentName "cleaner") .root.Values.operator.CleanerResources }}
{{ toYaml .root.Values.operator.CleanerResources | indent 10 }}
{{ else if and (eq .deploymentName "nodes-checker") .root.Values.operator.NodesCheckerResources }}
{{ toYaml .root.Values.operator.NodesCheckerResources | indent 10 }}
{{ else if and (eq .deploymentName "clear-cacher") .root.Values.operator.ClearCacherResources }}
{{ toYaml .root.Values.operator.ClearCacherResources | indent 10 }}
{{ else if and (eq .deploymentName "nas-checker") .root.Values.operator.NasCheckerResources }}
{{ toYaml .root.Values.operator.NasCheckerResources | indent 10 }}
{{ else }}
{{ toYaml .root.Values.operator.defaultResources | indent 10 }}
{{ end }}
{{- end }}