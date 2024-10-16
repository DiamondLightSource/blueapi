# Add Plans and Devices to your Blueapi Environment

:::{seealso}
[The bluesky documentation](https://blueskyproject.io/bluesky/main/index.html) for an introduction to the nature of plans and devices and why you would want to customize them for your experimental needs.
:::

Blueapi can be configured to load custom code at startup that defines plans and devices. The code must be in your Python environment (via `pip install <package>`) or your [scratch area](./edit-live.md).


## Format

Devices are made using the [dodal](https://github.com/DiamondLightSource/dodal) style available through factory functions like this:

:::{note}
The return type annotation `-> MyTypeOfDetector` is required as blueapi uses it to determine that this function creates a device. Meaning you can have a Python file where only some functions create devices and they will be automatically picked up.
:::

Similarly, these functions can be organized per-preference into files.
``` 
    from my_facility_devices import MyTypeOfDetector

    def my_detector(name: str) -> MyTypeOfDetector:
        return MyTypeOfDetector(name, {"other_config": "foo"})
```


See also: dodal for many more examples

An extra function to create the device is used to preserve side-effect-free imports. Each device must have its own factory function.


## Configuration

:::{seealso}
See also: [Configure the Application](./configure-app.md)
:::

First determine the import path of your code. If you were going to import it in a Python file, what would you put?
For example:
```python
    import my_plan_library.tomography.plans
```

You would add the following into your configuration file:
```yaml
    env:
      sources:
        - kind: planFunctions
          module: my_plan_library.tomography.plans
```

You can have as many sources for plans and devices as are needed.

:::{seealso}
[Home of Plans and Devices](../explanations/extension-code.md) for an introduction to the nature of plans and devices and why you would want to customize them for your experimental needs.
:::
