# Enable Persistent Volumes

BlueAPI can use persistent volumes as a scratch area. This allows the user to retain different environments for different versions of BlueAPI, and to avoid problems related to the shared file system such as permission issues.

## Configuration

:::{seealso}
[Configure the Application](./configure-app.md)
:::

The relevant configuration is below:

```{literalinclude} ../../tests/unit_tests/helm_examples/scratch-pv.yaml
:language: yaml
```

With both `initContainer.enabled` and `initContainer.persistentVolume.enabled` to `true`, BlueAPI will create or attempt to bind to an existing Persistent Volume Claim, which when fulfilled will be used as a scratch area.



## Reusing Persistent Volume Claims

BlueAPI can reuse existing PVCs by setting `initContainer.persistentVolume.existingClaimName`. When this is not set it defaults to `scratch-<blueapi-version>`. meaning the same Persistent Volume is reused when installing the same version of BlueAPI in a given namespace.

This can be set to any value to create and reuse arbitrarily named PVs.

## Directly Editing Persistent Volumes

The easiest way to interact with the created persistent volume is via the Kubernetes plugin for VSCode. [This is documented here.](https://diamondlightsource.github.io/python-copier-template/main/how-to/debug-in-cluster.html#debugging-in-the-cluster)
