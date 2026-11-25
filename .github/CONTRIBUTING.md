# Contribute to the project

Contributions and issues are most welcome! All issues and pull requests are
handled through [GitHub](https://github.com/DiamondLightSource/blueapi/issues).
Please check for existing issues before filing a new one. If you have a great
idea that involves big changes, please open an issue before making a pull
request. We want to make sure you don't spend your time coding something that
might not fit the scope of the project.

The [DAQ core team](https://github.com/orgs/DiamondLightSource/teams/developers-daq-core) maintains this repository.

## Issue or Discussion?

GitHub also offers
[discussions](https://github.com/DiamondLightSource/blueapi/discussions) as a
place to ask questions and share ideas. If your issue is open ended and it is
not obvious when it can be "closed", please raise it as a discussion instead.

## Reporting security issues

Please do not report security vulnerabilities in public issues. Use GitHub's
[private vulnerability reporting](https://github.com/DiamondLightSource/blueapi/security/advisories/new)
instead, so only the maintainers can see the report until a fix is released.

## Issue lifecycle

Every new issue starts with `needs-triage`. A core team member triages it by
swapping that label (and `awaiting-response`, if present) for one of the status
labels below. An issue has one status label at a time.

| Label | Meaning |
| --- | --- |
| `needs-triage` | New, not yet looked at by the core team |
| `needs-info` | Waiting on the reporter for details or a reproduction. A reply from the reporter moves it back to `needs-triage`. Otherwise it is marked `stale` after 30 days and closed 7 days later |
| `under-discussion` | Accepted as a problem; the solution is still being worked out |
| `ready` | Agreed, scoped and has acceptance criteria. Anyone can pick it up |
| `backlog` | Valid, but not planned for now |
| `help-wanted` | We would welcome an outside contribution. Combine with `onboarding` for good first issues |
| `wont-do` | Out of scope or rejected. The issue is closed with a comment explaining why |

Before starting on an issue, comment on it so it can be assigned to you and
work isn't duplicated.

### Support priority

Support staff can mark how urgently an issue affects beamline operations,
independently of the core team's own planning (`priority low`/`priority high`):

| Label | Meaning |
| --- | --- |
| `support: critical` | Blocking experiments or users right now |
| `support: high` | Significant impact, workaround is painful |
| `support: medium` | Noticeable impact, workaround exists |
| `support: low` | Minor or cosmetic |

The core team uses these labels as input when triaging and planning.

## Pull requests

- Link the issue it resolves (`Fixes #123`). Small fixes like typos don't need an issue.
- Keep pull requests small and focused on one change. Large changes are easier to review as a series.
- The title must follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, ...). CI checks this, and the title becomes the squashed commit message and release note.
- Add or update tests and docs alongside the code.
- Open as a draft while work is in progress, and mark it ready when you want a review.
- Pull requests need one approving review and passing CI before merging.

### Reviews

When a pull request is opened or marked ready for review, a member of the core
team is assigned as reviewer in turn (round-robin). This uses `CODEOWNERS` and
GitHub's [team review assignment](https://docs.github.com/en/organizations/organizing-members-into-teams/managing-code-review-settings-for-your-team). The assigned reviewer owns getting the pull request to a
decision. They may review it themselves or hand it to someone better placed.

Reviewers should:

- Be kind and explain the reasoning behind requests.
- Prefix optional suggestions with `nit:` so authors know what is blocking.
- Resolve their own threads once satisfied, and approve once there is nothing blocking.

### Response times

We aim to give every new issue and pull request a first response from the core
team within 3 days. A response can be a comment, a review or a triage
decision; it doesn't need to be a solution. If an issue still needs triage after
that time, a bot labels it `awaiting-response` and mentions the core team.

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
guides](https://diamondlightsource.github.io/python-copier-template/5.6.0/how-to.html).
