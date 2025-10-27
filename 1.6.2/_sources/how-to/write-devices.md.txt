# Write Devices for Blueapi

:::{seealso}
[Home of Plans and Devices](../explanations/extension-code.md) for information about where device code usually lives.
:::


## Format

:::{seealso}
[Dodal](https://github.com/DiamondLightSource/dodal) for many more examples
:::

Devices are made using the [dodal](https://github.com/DiamondLightSource/dodal) style available through factory functions like this:


```{literalinclude} ../../tests/unit_tests/code_examples/device_module.py
:language: python
```

The return type annotation `-> MyTypeOfDetector` is required as blueapi uses it to determine that this function creates a device. Meaning you can have a Python file where only some functions create devices, and they will be automatically picked up. Similarly, these functions can be organized per-preference into files. 

The device is created via a function rather than a global to preserve side-effect-free imports. Each device must have its own factory function.

:::{seealso}
[Numtracker integration](./integrate-with-numtracker.md) for how to configure where detectors write files.
:::
