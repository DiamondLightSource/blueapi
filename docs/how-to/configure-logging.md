
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

# Running BlueAPI on the Cluster

Services hosted on the cluster automatically have their stdout forwarded to Graylog via a service called fluentd. Due to this, BlueAPI services hosted on the cluster will always log to Graylog.

In this instance, the difference between enabling and disabling graylog in BlueAPI's configuration, is that fluentd only fowards plaintext logs, while BlueAPI's native graylog produces structured data with rich metadata included.
