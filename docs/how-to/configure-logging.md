
# Configure Logging

By default BlueAPI will log to stdout at the INFO level, but can be reconfigured to log at any level, and to output to Graylog.

As the BlueAPI logger is set at root level, it will recieve messages from all loggers in that same process that [allow propagation](https://docs.python.org/3/library/logging.html#logging.Logger.propagate).

When Graylog is enabled BlueAPI will continue to log to stdout.

# Cofiguration

An example logging config is shown below:
```...
worker:
  ...
    logging:
      level: "INFO"
      graylog:
        enabled: True
        host: "graylog-log-target.diamond.ac.uk"
        port: 12232
...
```

Here, BlueAPI will accept all messages are [INFO level and above](https://docs.python.org/3/library/logging.html#logging-levels) and will forward these to both the referenced Graylog address, and to stdout.
