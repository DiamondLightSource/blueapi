# blueapi

A Helm chart deploying a worker pod that runs Bluesky plans

**Homepage:** <https://github.com/DiamondLightSource/blueapi>

## Values

<table>
	<thead>
		<th>Key</th>
		<th>Type</th>
		<th>Default</th>
		<th>Description</th>
	</thead>
	<tbody>
		<tr>
			<td>affinity</td>
			<td>object</td>
			<td><pre lang="json">
{}
</pre>
</td>
			<td>May be required to run on specific nodes (e.g. the control machine)</td>
		</tr>
		<tr>
			<td>debug.enabled</td>
			<td>bool</td>
			<td><pre lang="json">
false
</pre>
</td>
			<td>If enabled, disables liveness and readiness probes, and does not start the service on startup This allows connecting to the pod and starting the service manually to allow debugging on the cluster</td>
		</tr>
		<tr>
			<td>extraEnvVars</td>
			<td>list</td>
			<td><pre lang="json">
[]
</pre>
</td>
			<td>Additional envVars to mount to the pod</td>
		</tr>
		<tr>
			<td>fullnameOverride</td>
			<td>string</td>
			<td><pre lang="json">
""
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>hostNetwork</td>
			<td>bool</td>
			<td><pre lang="json">
false
</pre>
</td>
			<td>May be needed for EPICS depending on gateway configuration</td>
		</tr>
		<tr>
			<td>image.pullPolicy</td>
			<td>string</td>
			<td><pre lang="json">
"IfNotPresent"
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>image.repository</td>
			<td>string</td>
			<td><pre lang="json">
"ghcr.io/diamondlightsource/blueapi"
</pre>
</td>
			<td>To use a container image that extends the blueapi one, set it here</td>
		</tr>
		<tr>
			<td>image.tag</td>
			<td>string</td>
			<td><pre lang="json">
""
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>imagePullSecrets</td>
			<td>list</td>
			<td><pre lang="json">
[]
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>ingress</td>
			<td>object</td>
			<td><pre lang="json">
{
  "annotations": {},
  "className": "nginx",
  "enabled": false,
  "hosts": [
    {
      "host": "example.diamond.ac.uk",
      "paths": [
        {
          "path": "/",
          "pathType": "Prefix"
        }
      ]
    }
  ],
  "tls": []
}
</pre>
</td>
			<td>Configuring and enabling an ingress allows blueapi to be served at a nicer address, e.g. ixx-blueapi.diamond.ac.uk</td>
		</tr>
		<tr>
			<td>ingress.hosts[0]</td>
			<td>object</td>
			<td><pre lang="json">
{
  "host": "example.diamond.ac.uk",
  "paths": [
    {
      "path": "/",
      "pathType": "Prefix"
    }
  ]
}
</pre>
</td>
			<td>Request a host from https://jira.diamond.ac.uk/servicedesk/customer/portal/2/create/91 of the form ixx-blueapi.diamond.ac.uk. Note: pathType: Prefix is required in Diamond's clusters</td>
		</tr>
		<tr>
			<td>initContainer</td>
			<td>object</td>
			<td><pre lang="json">
{
  "enabled": false,
  "persistentVolume": {
    "enabled": false,
    "existingClaimName": ""
  }
}
</pre>
</td>
			<td>Configure the initContainer that checks out the scratch configuration repositories</td>
		</tr>
		<tr>
			<td>initContainer.persistentVolume.enabled</td>
			<td>bool</td>
			<td><pre lang="json">
false
</pre>
</td>
			<td>Whether to use a persistent volume in the cluster or check out onto the mounted host filesystem If persistentVolume.enabled: False, mounts scratch.root as scratch.root in the container</td>
		</tr>
		<tr>
			<td>initContainer.persistentVolume.existingClaimName</td>
			<td>string</td>
			<td><pre lang="json">
""
</pre>
</td>
			<td>May be set to an existing persistent volume claim to re-use the volume, else a new one is created for each blueapi release</td>
		</tr>
		<tr>
			<td>livenessProbe</td>
			<td>object</td>
			<td><pre lang="json">
{
  "failureThreshold": 3,
  "httpGet": {
    "path": "/healthz",
    "port": "http"
  },
  "periodSeconds": 10
}
</pre>
</td>
			<td>Liveness probe, if configured kubernetes will kill the pod and start a new one if failed consecutively. This is automatically disabled when in debug mode.</td>
		</tr>
		<tr>
			<td>nameOverride</td>
			<td>string</td>
			<td><pre lang="json">
""
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>nodeSelector</td>
			<td>object</td>
			<td><pre lang="json">
{}
</pre>
</td>
			<td>May be required to run on specific nodes (e.g. the control machine)</td>
		</tr>
		<tr>
			<td>podAnnotations</td>
			<td>object</td>
			<td><pre lang="json">
{}
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>podLabels</td>
			<td>object</td>
			<td><pre lang="json">
{}
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>podSecurityContext</td>
			<td>object</td>
			<td><pre lang="json">
{}
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>readinessProbe</td>
			<td>object</td>
			<td><pre lang="json">
{
  "failureThreshold": 2,
  "httpGet": {
    "path": "/healthz",
    "port": "http"
  },
  "periodSeconds": 10
}
</pre>
</td>
			<td>Readiness probe, if configured kubernetes will not route traffic to this pod if failed consecutively. This could allow the service time to recover if it is being overwhelmed by traffic, but without the to ability to load balance or scale up/outwards, upstream services will need to know to back off. This is automatically disabled when in debug mode.</td>
		</tr>
		<tr>
			<td>resources</td>
			<td>object</td>
			<td><pre lang="json">
{
  "limits": {
    "cpu": "2000m",
    "memory": "4000Mi"
  },
  "requests": {
    "cpu": "200m",
    "memory": "400Mi"
  }
}
</pre>
</td>
			<td>Sets the compute resources available to the pod. These defaults are appropriate when using debug mode or an internal PVC and therefore running VS Code server in the pod. In the Diamond cluster, requests must be >= 0.1*limits When not using either of the above, the limits may be lowered. When idle but connected, blueapi consumes ~400MB of memory and 1% cpu and may struggle when allocated less.</td>
		</tr>
		<tr>
			<td>restartOnConfigChange</td>
			<td>bool</td>
			<td><pre lang="json">
true
</pre>
</td>
			<td>If enabled the blueapi pod will restart on changes to `worker`</td>
		</tr>
		<tr>
			<td>securityContext.runAsNonRoot</td>
			<td>bool</td>
			<td><pre lang="json">
true
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>securityContext.runAsUser</td>
			<td>int</td>
			<td><pre lang="json">
1000
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>service.port</td>
			<td>int</td>
			<td><pre lang="json">
80
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>service.type</td>
			<td>string</td>
			<td><pre lang="json">
"ClusterIP"
</pre>
</td>
			<td>To make blueapi available on an IP outside of the cluster prior to an Ingress being created, change this to LoadBalancer</td>
		</tr>
		<tr>
			<td>serviceAccount.annotations</td>
			<td>object</td>
			<td><pre lang="json">
{}
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>serviceAccount.automount</td>
			<td>bool</td>
			<td><pre lang="json">
true
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>serviceAccount.create</td>
			<td>bool</td>
			<td><pre lang="json">
false
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>serviceAccount.name</td>
			<td>string</td>
			<td><pre lang="json">
""
</pre>
</td>
			<td></td>
		</tr>
		<tr>
			<td>startupProbe</td>
			<td>object</td>
			<td><pre lang="json">
{
  "failureThreshold": 5,
  "httpGet": {
    "path": "/healthz",
    "port": "http"
  },
  "periodSeconds": 10
}
</pre>
</td>
			<td>A more lenient livenessProbe to allow the service to start fully. This is automatically disabled when in debug mode.</td>
		</tr>
		<tr>
			<td>tolerations</td>
			<td>list</td>
			<td><pre lang="json">
[]
</pre>
</td>
			<td>May be required to run on specific nodes (e.g. the control machine)</td>
		</tr>
		<tr>
			<td>tracing</td>
			<td>object</td>
			<td><pre lang="json">
{
  "otlp": {
    "enabled": false,
    "protocol": "http/protobuf",
    "server": {
      "host": "http://opentelemetry-collector.tracing",
      "port": 4318
    }
  }
}
</pre>
</td>
			<td>Configure tracing: opentelemetry-collector.tracing should be available in all Diamond clusters</td>
		</tr>
		<tr>
			<td>volumeMounts</td>
			<td>list</td>
			<td><pre lang="json">
[
  {
    "mountPath": "/config",
    "name": "worker-config",
    "readOnly": true
  }
]
</pre>
</td>
			<td>Additional volumeMounts on the output StatefulSet definition. Define how volumes are mounted to the container referenced by using the same name.</td>
		</tr>
		<tr>
			<td>volumes</td>
			<td>list</td>
			<td><pre lang="json">
[]
</pre>
</td>
			<td>Additional volumes on the output StatefulSet definition. Define volumes from e.g. Secrets, ConfigMaps or the Filesystem</td>
		</tr>
		<tr>
			<td>worker</td>
			<td>object</td>
			<td><pre lang="json">
{
  "api": {
    "url": "http://0.0.0.0:8000/"
  },
  "env": {
    "sources": [
      {
        "kind": "planFunctions",
        "module": "dodal.plans"
      },
      {
        "kind": "planFunctions",
        "module": "dodal.plan_stubs.wrapped"
      }
    ]
  },
  "logging": {
    "graylog": {
      "enabled": false,
      "url": "tcp://graylog-log-target.diamond.ac.uk:12232/"
    },
    "level": "INFO"
  },
  "scratch": {
    "repositories": [],
    "root": "/blueapi-plugins/scratch"
  },
  "stomp": {
    "auth": {
      "password": "guest",
      "username": "guest"
    },
    "enabled": false,
    "url": "tcp://rabbitmq:61613/"
  }
}
</pre>
</td>
			<td>Config for the worker goes here, will be mounted into a config file</td>
		</tr>
		<tr>
			<td>worker.api.url</td>
			<td>string</td>
			<td><pre lang="json">
"http://0.0.0.0:8000/"
</pre>
</td>
			<td>0.0.0.0 required to allow non-loopback traffic If using hostNetwork, the port must be free on the host</td>
		</tr>
		<tr>
			<td>worker.env.sources</td>
			<td>list</td>
			<td><pre lang="json">
[
  {
    "kind": "planFunctions",
    "module": "dodal.plans"
  },
  {
    "kind": "planFunctions",
    "module": "dodal.plan_stubs.wrapped"
  }
]
</pre>
</td>
			<td>modules (must be installed in the venv) to fetch devices/plans from</td>
		</tr>
		<tr>
			<td>worker.logging</td>
			<td>object</td>
			<td><pre lang="json">
{
  "graylog": {
    "enabled": false,
    "url": "tcp://graylog-log-target.diamond.ac.uk:12232/"
  },
  "level": "INFO"
}
</pre>
</td>
			<td>Configures logging. Port 12231 is the `dodal` input on graylog which will be renamed `blueapi`</td>
		</tr>
		<tr>
			<td>worker.scratch</td>
			<td>object</td>
			<td><pre lang="json">
{
  "repositories": [],
  "root": "/blueapi-plugins/scratch"
}
</pre>
</td>
			<td>If initContainer is enabled the default branch of python projects in this section are installed into the venv *without their dependencies*</td>
		</tr>
		<tr>
			<td>worker.stomp</td>
			<td>object</td>
			<td><pre lang="json">
{
  "auth": {
    "password": "guest",
    "username": "guest"
  },
  "enabled": false,
  "url": "tcp://rabbitmq:61613/"
}
</pre>
</td>
			<td>Message bus configuration for returning status to GDA/forwarding documents downstream Password may be in the form ${ENV_VAR} to be fetched from an environment variable e.g. mounted from a SealedSecret </td>
		</tr>
	</tbody>
</table>

