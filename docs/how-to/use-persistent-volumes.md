# Enable Persistent Volumes

BlueAPI can use persistent volumes as a scratch area. This allows the user to retain different environments for different versions of BlueAPI, and to avoid problems related to the shared file system such as permission issues.

## Configuration

:::{seealso}
[Configure the Application](./configure-app.md)
:::

The relevant configuration is below:

```yaml
# -- Configure the initContainer that checks out the scratch configuration repositories
initContainer:
  enabled: false
  persistentVolume:
    # -- Whether to use a persistent volume in the cluster or check out onto the mounted host filesystem
    # If persistentVolume.enabled: False, mounts scratch.root as scratch.root in the container
    enabled: false
    # -- May be set to an existing persistent volume claim to re-use the volume, else a new one is created for each blueapi release
    existingClaimName: ""
```

By setting both `initContainer.enabled` and `initContainer.persistentVolume.enabled` to `true` BlueAPI will produce or reuse a Persistent Volume Claim, which when fulfilled will be used as a scratch directory.


This may require additional resources. In past implementations, setting `resources.cpu` to `500m` has been sufficient. The default values are shown below:
```yaml
...
resources:
  # We usually recommend not to specify default resources and to leave this as a conscious
  # choice for the user. This also increases chances charts run on environments with little
  # resources, such as Minikube. If you do want to specify resources, uncomment the following
  # lines, adjust them as necessary, and remove the curly braces after 'resources:'.
  limits:
    cpu: 2000m
    memory: 4000Mi
  requests:
    cpu: 200m
    memory: 400Mi
```

Finally, if installing BlueAPI from source rather than from the packaged helm chart `image.tag` value must to set to a recent BlueAPI release, else the default `0.1.0` will pull an image without the required features.
```yaml
# This sets the container image more information can be found here: https://kubernetes.io/docs/concepts/containers/images/
image:
  # -- To use a container image that extends the blueapi one, set it here
  repository: ghcr.io/diamondlightsource/blueapi
  # This sets the pull policy for images.
  pullPolicy: IfNotPresent
  # Overrides the image tag whose default is the chart appVersion.
  tag: ""
  ```
