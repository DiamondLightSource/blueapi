# Add Plans and Devices to your Blueapi Environment

:::{seealso}
[The bluesky documentation](https://blueskyproject.io/bluesky/main/index.html) for an introduction to the nature of plans and devices and why you would want to customize them for your experimental needs.
:::

Blueapi can be configured to load custom code at startup that defines plans and devices. The code must be in your Python environment (via `pip install <package>`) or your [scratch area](./edit-live.md).


## Configuration

:::{seealso}
[Configure the Application](./configure-app.md)
:::

First determine the import path of your code. If you were going to import it in a Python file, what would you put?
For example:
```python
import my_plan_library.tomography.plans
```

To add plans, you would add the following into your configuration file:

```{literalinclude} ../../tests/unit_tests/valid_example_config/plan_functions.yaml
:language: yaml
```


Devices are added similarly, using `dodal` as the `kind`, like so: 
```{literalinclude} ../../tests/unit_tests/valid_example_config/plans_and_devices.yaml
:language: yaml
```


You can have as many sources for plans and devices as are needed.

:::{seealso}
[Home of Plans and Devices](../explanations/extension-code.md) for an introduction to the nature of plans and devices and why you would want to customize them for your experimental needs.
:::
