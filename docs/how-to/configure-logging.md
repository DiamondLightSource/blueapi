
# Configure Logging

By default BlueAPI will log to stdout at the [INFO level](https://docs.python.org/3/library/logging.html#logging-levels), but can be reconfigured to log at any level, and to output to Graylog.

When Graylog is enabled, BlueAPI will continue to log to stdout.

# BlueAPI Cofiguration

:::{seealso}
[Configure the Application](./configure-app.md)
:::

An example logging config is shown below:
```
worker:
    logging:
      level: "INFO"
      graylog:
        enabled: True
        host: "graylog-log-target.diamond.ac.uk"
        port: 12232
```

Here, BlueAPI will accept all messages are INFO level and above and will forward these to both the referenced Graylog address, and to stdout.

# Instrumenting Libraries
To instrument to a custom module in BlueAPI, instantiate a logger from the [standard library logging package, then use any of its log methods](https://docs.python.org/3/library/logging.html#logger-objects).

BlueAPI is written to intercept logs from any python code it executes.

```
import logging
logger = logging.getLogger(__name__)
logger.info("FOO")
```

# Running BlueAPI on the Cluster

Services hosted on the cluster automatically have their stdout forwarded to Graylog via a service called fluentd. Due to this, BlueAPI services hosted on the cluster will always log to Graylog.

In this instance, the difference between enabling and disabling graylog in BlueAPI's configuration, is that fluentd only fowards plaintext logs, while BlueAPI's native graylog produces structured data with rich metadata included.

# Were to Find Logs

By default logs can be found wherever your stdout is. 

If Graylog is enabled, logs will be forwarded to whichever Graylog instance the configuration addresses. By default this is the main Diamond instance, which can be accessed via [graylog.diamond.ac.uk](https://graylog.diamond.ac.uk/)

If your BlueAPI server is running on the cluster, stdout is likely being forwarded to the above Graylog instance.
