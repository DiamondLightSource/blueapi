
# Configure Logging

By default BlueAPI will log to stdout at the [INFO level](https://docs.python.org/3/library/logging.html#logging-levels), but can be reconfigured to log at any level, and to output to Graylog.


To add logging to a custom module in BlueAPI, instantiate a logger from the [standard library logging package, then use any of its log methods](https://docs.python.org/3/library/logging.html#logger-objects).

When Graylog is enabled, BlueAPI will continue to log to stdout.

Services hosted on the cluster automatically have their stdout forwarded to Graylog via a service called fluentd. Due to this, 
In BlueAPI, if your config's `worker.logging.graylog.enabled` is `True` (if Graylog is enabed), then the `fluentd-ignore` pod annotation is automatically set to `True`. This disables stdout forwarding to avoid log duplication.


# Cofiguration

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
