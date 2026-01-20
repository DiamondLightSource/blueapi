
# Configure Logging

By default BlueAPI will log to stdout at the [INFO level](https://docs.python.org/3/library/logging.html#logging-levels), but can be reconfigured to log at any level, and to output to Graylog.

When logging to [Graylog](https://graylog.org) is enabled, BlueAPI will also continue to log to stdout.

# BlueAPI Cofiguration

:::{seealso}
[Configure the Application](./configure-app.md)
:::

An example logging config is shown below:
```{literalinclude} ../../tests/unit_tests/valid_example_config/graylog.yaml
:language: yaml
```

With this configuration, all logs at INFO level or above will be logged to both stdout and the configured graylog.

# Instrumenting Libraries
To instrument to a custom module in BlueAPI, instantiate a logger from the [standard library logging package, then use any of its log methods](https://docs.python.org/3/library/logging.html#logger-objects).

BlueAPI is configured to handle logging from any python code it executes.

```
import logging
LOGGER = logging.getLogger(__name__)
LOGGER.info("FOO")
```

# Kubernetes

Services hosted on the DLS clusters automatically have their stdout forwarded to Graylog via a service called fluentd. Due to this, BlueAPI services hosted on the cluster will always log to Graylog.

When BlueAPI's native Graylog support is enabled it forwards structured data rather than plaintext.

When BlueAPI's native Graylog is enabled fluentd will be automatically disabled to avoid log duplication.

# Where to Find Logs

By default logs can be found wherever your stdout is. 

If Graylog is enabled, logs will be forwarded to whichever Graylog instance the configuration addresses. By default this is the main Diamond instance, which can be accessed via [graylog.diamond.ac.uk](https://graylog.diamond.ac.uk/)

If your BlueAPI server is running on the Diamond cluster, stdout is likely being forwarded to the above Graylog instance.

# Log Message Structure

When structured logging via Graylog is enabled, BlueAPI will bundle the log message and instrument name (e.g. i22) into a JSON blob. Also included is other standard logging data, such as a timestamp.
