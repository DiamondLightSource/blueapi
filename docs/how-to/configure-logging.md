
# Configure Logging

By default BlueAPI will log to stdout at the [INFO level](https://docs.python.org/3/library/logging.html#logging-levels), but can be reconfigured to log at any level, and to output to Graylog.

As the BlueAPI handlers are set at root level, they will recieve messages from all loggers in the same process that [allow propagation](https://docs.python.org/3/library/logging.html#logging.Logger.propagate).

To add logging to a custom module in BlueAPI, simply instantiate a logger from the [standard library logging package, then use any of its log methods](https://docs.python.org/3/library/logging.html#logger-objects). Propagation is enabled by default.

When Graylog is enabled, BlueAPI will continue to log to stdout.

Services hosted on the cluster automatically have their stdout forwarded to Graylog via a service called fluentd. In BlueAPI, if your config's `worker.logging.graylog.enabled` is `True`, then the `fluentd-ignore` pod annotation is automatically set to `True`. This disables stdout forwarding.

# Cofiguration

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
