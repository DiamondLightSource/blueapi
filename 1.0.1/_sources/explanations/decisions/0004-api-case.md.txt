# 4. API Model Case

Date: 2023-05-23

## Status

Accepted

## Context

Considering whether keys in JSON blobs from the API should be in snake_case or camelCase.
This includes plan parameters which may be user-defined.

## Decision

The priority is not to confuse users, so we will not alias any field names defined in Python.

## Consequences

Most code will be written with pep8 enforcers which means most field names will be snake_case.
Some user defined ones may differ.
