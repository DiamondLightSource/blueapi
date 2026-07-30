# Home of Plans and Devices

## Dodal

[Dodal](https://github.com/DiamondLightSource/dodal) is a repository for DLS device configuration, providing classes and factory functions for devices used at DLS.
For specific advice on creating new device types and adding them to new or existing beamlines, see [Create a Beamline](https://diamondlightsource.github.io/dodal/main/how-to/create-beamline.html) and [Device Standards](https://diamondlightsource.github.io/dodal/main/reference/device-standards.html) in the dodal documentation.

## Other Repositories

Plans and devices can be in any pip-installable package, such as:

* A package on pypi
* A GitHub repository
* A local directory via the [scratch area](../how-to/edit-live.md).

The easiest place to put the code is a repository created with the [`python-copier-template`](https://diamondlightsource.github.io/python-copier-template/main/index.html). Which can then become any of the above. [Example for the I22 beamline](https://github.com/DiamondLightSource/i22-bluesky).

:::{seealso}
Guide to setting up a new Python project with an environment and a standard set of tools: [`Create a new repo from the template`](https://diamondlightsource.github.io/python-copier-template/main/tutorials/create-new.html)
:::
