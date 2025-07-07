# 5. Connect all dodal devices during startup

Date: 10-12-2024

## Status

Accepted

## Context

Currently, Dodal devices are not automatically connected when they are created.

## Decision

All Dodal devices will be configured to automatically connect upon creation, ensuring they are ready for use immediately after initialization.

## Consequences

- Devices that fail to connect during startup will remain disconnected.
- Additional measures will need to be implemented to ensure such devices are identified and reconnected promptly.
