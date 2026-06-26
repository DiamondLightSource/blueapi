# Architecture

Blueapi performs a number of tasks:

* Managing the Bluesky [RunEngine](https://nsls-ii.github.io/bluesky/run_engine_api.html), giving it instructions and handling its errors. Traditionally this job has been done by a human with an [IPython](https://ipython.org/) terminal, so it requires automating.
* Maintaining a registry of plans and devices. In the aforementioned IPython_ case, these would have just been global variables.
* Communicating with the outside world, accepting instructions to run plans, providing updates on plan progress etc.

These responsibilities are kept separate in the codebase to ensure a clean, maintainable architecture.

![blueapi main components](../images/blueapi.png)


Above are the main components of blueapi. The main process houses the REST API and manages the subprocess, which wraps the `RunEngine`, devices and external connections.
