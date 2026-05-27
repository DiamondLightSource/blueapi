# 3. No Queues

Date: 2023-05-22

## Status

Accepted

## Context

In asking whether this service should hold and execute a queue of tasks.

## Decision

We will not hold any queues. The worker can execute one task at a time and will return
an error if asked to execute one task while another is running. Queueing should be the
responsibility of a different service.

## Consequences

The API must be kept queue-free, although transactions are permitted where the server
caches requests.
