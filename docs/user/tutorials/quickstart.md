---
title: Quickstart Guide
---

<div class="seealso">

Assumes you have completed
<span class="title-ref">./installation</span>.

</div>

Blueapi acts as a worker that can run bluesky plans against devices for
a specific laboratory setup. It can control devices to collect data and
export events to tell downstream services about the data it has
collected.

# Start ActiveMQ

The worker requires a running instance of ActiveMQ, the simplest way to
start it is to run it via a container:

<div class="tab-set">

<div class="tab-item">

Docker

``` shell
docker run -it --rm --net host rmohr/activemq:5.15.9-alpine
```

</div>

<div class="tab-item">

Podman

``` shell
podman run -it --rm --net host rmohr/activemq:5.15.9-alpine
```

</div>

</div>

# Start Worker

To start the worker:

``` shell
blueapi serve
```

The worker can also be started using a custom config file:

``` shell
blueapi --config path/to/file serve
```

# Test that the Worker is Running

Blueapi comes with a CLI so that you can query and control the worker
from the terminal.

``` shell
blueapi controller plans
```

The above command should display all plans the worker is capable of
running.

<div class="seealso">

Full CLI reference: <span class="title-ref">../reference/cli</span>

</div>
