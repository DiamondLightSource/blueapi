# Contribute to the project

Contributions and issues are most welcome! All issues and pull requests are
handled through [GitHub](https://github.com/DiamondLightSource/blueapi/issues).
Also, please check for any existing issues before filing a new one. If you have
a great idea but it involves big changes, please file a ticket before making a
pull request! We want to make sure you don't spend your time coding something
that might not fit the scope of the project.

## Issue or Discussion?

Github also offers
[discussions](https://github.com/DiamondLightSource/blueapi/discussions) as a
place to ask questions and share ideas. If your issue is open ended and it is
not obvious when it can be "closed", please raise it as a discussion instead.

## Code Coverage

While 100% code coverage does not make a library bug-free, it significantly
reduces the number of easily caught bugs! Please make sure coverage remains the
same or is improved by a pull request!

## Developer Information

It is recommended that developers use a [vscode
devcontainer](https://code.visualstudio.com/docs/devcontainers/containers). This
repository contains configuration to set up a containerized development
environment that suits its own needs.

This project was created using the [Diamond Light Source Copier
Template](https://github.com/DiamondLightSource/python-copier-template) for
Python projects.

For more information on common tasks like setting up a developer environment,
running the tests, and setting a pre-commit hook, see the template's [How-to
guides](https://diamondlightsource.github.io/python-copier-template/5.5.0/how-to.html).

## LLM and genAI policy

*tl;dr - If other contributors can't see any output of your LLM tools, it's
probably ok*

You remain fully responsible for all contributions to the project and must be
able to respond to reviews and comments without relying on LLM tools.

### No LLM-Generated Communication

LLM output MUST NOT be used in any communication to other maintainers. This
includes:

* Issues
* PR descriptions
* PR reviews
* Commit messages
* Comments/replies

An exception may be made for selective quotes/excerpts in the context of a
wider discussion. Any such use should be sparing and explicitly disclosed.

Using LLMs to review other contributors' PRs is not acceptable without fully
understanding any feedback and being able to comment in your own words and
respond to replies. If the contributor wanted LLM output they would request it
directly.

A consequence of these restrictions is that no autonomous agents may interact
with the project in any way.

### LLM Assisted Code Contributions

LLMs may be used if required as a developer aid but should not replace
understanding when writing code.

As a general rule it is ok to use LLMs to:
* Help explain the existing codebase or third party libraries being used
* Help debug an issue
* Review your own code or documentation prior to submission
* Suggest approaches for adding features or fixes for personal use only - do not
  post LLM suggestions as proposed fixes for issues raised by other
  contributors
* Generate trivial or minor changes that would be straightforward but time
  consuming to complete manually

For larger or more complex changes, code generation should be used very
sparingly.

It is highly likely that fully understanding the behaviour and implications of
generated code would take as long as (if not longer than) writing it manually.
This is especially true for reviewers of your contribution. Please be respectful
of their time when creating large changes.

If the solution is not something you would have been able to implement without
the LLM, time should be spent increasing understanding around the project before
attempting a fix.

LLM use MUST be disclosed where used.

### LLM Generated Documentation

Documentation is intended for people to read and it is strongly recommended that
it is written manually.

If it helps ensure the documentation stays in sync with the code, LLMs may be
used to review new docs for correctness/completeness or to ensure code changes
update any relevant docs.
