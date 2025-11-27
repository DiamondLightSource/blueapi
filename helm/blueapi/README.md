# blueapi

A Helm chart deploying a worker pod that runs Bluesky plans

**Homepage:** <https://github.com/DiamondLightSource/blueapi>

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| affinity | object | `{}` | May be required to run on specific nodes (e.g. the control machine) |
| debug.enabled | bool | `false` | If enabled, runs debugpy, allowing port-forwarding to expose port 5678 or attached vscode instance |
| debug.log_to_stderr | bool | `false` | If enabled configures debugpy to use the option `--log-to-stderr` |
| debug.suspend | bool | `false` | If enabled does not start the service on startup This allows connecting to the pod and starting the service manually to allow debugging on the cluster |
| extraEnvVars | list | `[]` | Additional envVars to mount to the pod |
| fullnameOverride | string | `""` |  |
| global | object | `{}` | Not used, but must be present for validation when using as a dependency of another chart |
| hostNetwork | bool | `false` | May be needed for EPICS depending on gateway configuration |
| image.pullPolicy | string | `"IfNotPresent"` |  |
| image.repository | string | `"ghcr.io/diamondlightsource/blueapi"` | To use a container image that extends the blueapi one, set it here |
| image.tag | string | `""` |  |
| imagePullSecrets | list | `[]` |  |
| ingress | object | `{"annotations":{},"className":"nginx","enabled":false,"hosts":[{"host":"example.diamond.ac.uk","paths":[{"path":"/","pathType":"Prefix"}]}],"tls":[]}` | Configuring and enabling an ingress allows blueapi to be served at a nicer address, e.g. ixx-blueapi.diamond.ac.uk |
| ingress.hosts[0] | object | `{"host":"example.diamond.ac.uk","paths":[{"path":"/","pathType":"Prefix"}]}` | Request a host from https://jira.diamond.ac.uk/servicedesk/customer/portal/2/create/91 of the form ixx-blueapi.diamond.ac.uk. Note: pathType: Prefix is required in Diamond's clusters |
| initContainer | object | `{"enabled":false,"persistentVolume":{"enabled":false,"existingClaimName":""}}` | Configure the initContainer that checks out the scratch configuration repositories |
| initContainer.persistentVolume.enabled | bool | `false` | Whether to use a persistent volume in the cluster or check out onto the mounted host filesystem If persistentVolume.enabled: False, mounts scratch.root as scratch.root in the container |
| initContainer.persistentVolume.existingClaimName | string | `""` | May be set to an existing persistent volume claim to re-use the volume, else a new one is created for each blueapi release |
| initResources | object | `{}` | Override resources for init container. By default copies resources of main container. |
| livenessProbe | object | `{"failureThreshold":3,"httpGet":{"path":"/healthz","port":"http"},"periodSeconds":10}` | Liveness probe, if configured kubernetes will kill the pod and start a new one if failed consecutively. This is automatically disabled when in debug mode. |
| nameOverride | string | `""` |  |
| nodeSelector | object | `{}` | May be required to run on specific nodes (e.g. the control machine) |
| podAnnotations | object | `{}` |  |
| podLabels | object | `{}` |  |
| podSecurityContext | object | `{}` |  |
| readinessProbe | object | `{"failureThreshold":2,"httpGet":{"path":"/healthz","port":"http"},"periodSeconds":10}` | Readiness probe, if configured kubernetes will not route traffic to this pod if failed consecutively. This could allow the service time to recover if it is being overwhelmed by traffic, but without the to ability to load balance or scale up/outwards, upstream services will need to know to back off. This is automatically disabled when in debug mode. |
| resources | object | `{"limits":{"cpu":"2000m","memory":"4000Mi"},"requests":{"cpu":"200m","memory":"400Mi"}}` | Sets the compute resources available to the pod. These defaults are appropriate when using debug mode or an internal PVC and therefore running VS Code server in the pod. In the Diamond cluster, requests must be >= 0.1*limits When not using either of the above, the limits may be lowered. When idle but connected, blueapi consumes ~400MB of memory and 1% cpu and may struggle when allocated less. |
| restartOnConfigChange | bool | `true` | If enabled the blueapi pod will restart on changes to `worker` |
| securityContext.runAsNonRoot | bool | `true` |  |
| securityContext.runAsUser | int | `1000` |  |
| service.port | int | `80` |  |
| service.type | string | `"ClusterIP"` | To make blueapi available on an IP outside of the cluster prior to an Ingress being created, change this to LoadBalancer |
| serviceAccount.annotations | object | `{}` |  |
| serviceAccount.automount | bool | `true` |  |
| serviceAccount.create | bool | `false` |  |
| serviceAccount.name | string | `""` |  |
| startupProbe | object | `{"failureThreshold":5,"httpGet":{"path":"/healthz","port":"http"},"periodSeconds":10}` | A more lenient livenessProbe to allow the service to start fully. This is automatically disabled when in debug mode. |
| tolerations | list | `[]` | May be required to run on specific nodes (e.g. the control machine) |
| tracing | object | `{"otlp":{"enabled":false,"protocol":"http/protobuf","server":{"host":"http://opentelemetry-collector.tracing","port":4318}}}` | Configure tracing: opentelemetry-collector.tracing should be available in all Diamond clusters |
| volumeMounts | list | `[{"mountPath":"/config","name":"worker-config","readOnly":true}]` | Additional volumeMounts on the output StatefulSet definition. Define how volumes are mounted to the container referenced by using the same name. |
| volumes | list | `[]` | Additional volumes on the output StatefulSet definition. Define volumes from e.g. Secrets, ConfigMaps or the Filesystem |
| worker | object | `{"api":{"url":"http://0.0.0.0:8000/"},"env":{"sources":[{"kind":"planFunctions","module":"dodal.plans"},{"kind":"planFunctions","module":"dodal.plan_stubs.wrapped"}]},"logging":{"graylog":{"enabled":false,"url":"tcp://graylog-log-target.diamond.ac.uk:12231/"},"level":"INFO"},"scratch":{"repositories":[],"root":"/blueapi-plugins/scratch"},"stomp":{"auth":{"password":"guest","username":"guest"},"enabled":false,"url":"tcp://rabbitmq:61613/"}}` | Config for the worker goes here, will be mounted into a config file |
| worker.api.url | string | `"http://0.0.0.0:8000/"` | 0.0.0.0 required to allow non-loopback traffic If using hostNetwork, the port must be free on the host |
| worker.env.sources | list | `[{"kind":"planFunctions","module":"dodal.plans"},{"kind":"planFunctions","module":"dodal.plan_stubs.wrapped"}]` | modules (must be installed in the venv) to fetch devices/plans from |
| worker.logging | object | `{"graylog":{"enabled":false,"url":"tcp://graylog-log-target.diamond.ac.uk:12231/"},"level":"INFO"}` | Configures logging. Port 12231 is the `dodal` input on graylog which will be renamed `blueapi` |
| worker.scratch | object | `{"repositories":[],"root":"/blueapi-plugins/scratch"}` | If initContainer is enabled the default branch of python projects in this section are installed into the venv *without their dependencies* |
| worker.stomp | object | `{"auth":{"password":"guest","username":"guest"},"enabled":false,"url":"tcp://rabbitmq:61613/"}` | Message bus configuration for returning status to GDA/forwarding documents downstream Password may be in the form ${ENV_VAR} to be fetched from an environment variable e.g. mounted from a SealedSecret |
