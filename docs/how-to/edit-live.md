# Edit Plans and Device Live

You may want to tweak/edit your plans and devices live, i.e. without having to make a new release of a Python module, `pip install` it and restart blueapi. Blueapi can be configured to use a special directory called the "scratch area" where source code can be checked out and installed in [development mode](https://setuptools.pypa.io/en/latest/userguide/development_mode.html).

## Configuration

Blueapi can be configured to install editable Python packages from a chosen directory:

```yaml
# my-scratch.yaml

scratch:
    root: /path/to/my/scratch/directory
    # Required GID for the scratch area
    required_gid: 12345
    repositories:
        # Repository for DLS devices
        - name: dodal
          remote_url: https://github.com/DiamondLightSource/dodal.git

        # Example repository full of custom plans for a particular science technique
        - name: mx-bluesky
          remote_url: https://github.com/DiamondLightSource/mx-bluesky.git
```

Note the `required_gid` field, which is useful for stopping blueapi from locking the files it clones
to a particular owner.

## Synchronization

Blueapi will synchronize reality with the configuration if you run

```
blueapi -c my-scratch.yaml setup-scratch
```

The goal of synchronization is to make the scratch directory resemble the YAML specification without accidentally overwriting uncommited/unpushed changes that may already be there. For each specified repository, blueapi will clone it if it does not exist and otherwise ignore it. If it exists in a broken state, this can cause problems, and you may have to manually delete it from your scratch area. 

## Reloading

:::{warning}
This will abort any running plan and delete and re-initialize all ophyd devices
:::

If you add or remove packages from the scratch area, you will need to restart blueapi. However, if you edit code that is already checked out you can tell the server to perform a hot reload via

```
blueapi controller env -r
```

## Kubernetes

The helm chart can be configured to mount a scratch area from the
host machine, include the following in your `values.yaml`:

```yaml
  initContainer:
    enabled: true
    scratch:
      root: path/to/scratch/area  # e.g. /dls_sw/<my_beamline>/software/blueapi/scratch
      repositories: []
```


The scratch folder that you're pointing to must exist, not already have a copy of the repositories that will be cloned into it and have correct permissions e.g.

```
cd /dls_sw/<my_beamline>/software/blueapi/
mkdir scratch
chmod o+wrX -R scratch
```

BlueAPI will then checkout the `main` branch of any specified repos into this scratch folder.
