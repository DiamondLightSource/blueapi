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
