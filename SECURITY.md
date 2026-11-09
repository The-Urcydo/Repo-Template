# Security policy

## Reporting a vulnerability

Please report security problems privately. Do not open a public issue with the details.

Use GitHub's private vulnerability reporting: open the **Security** tab of this repository and choose **Report a vulnerability**. If that option is not available to you, open an issue that says you have a security concern, without any details, and ask for a private way to share them.

We will acknowledge your report as soon as we can and keep you informed while it is looked at. This is a small project, so there is no fixed response time.

## What is in scope

This repository is a Copier template, so the code that can affect you is the code the template generates and runs:

- the standard-library Python tools under `template/tools/`, which run inside generated projects;
- the post-generation tasks in `copier.yml`. Copier's `--trust` flag lets the template run two of its own scripts (`tools/sync_indexes.py` and `tools/sync_agents.py`) after generating a project. Read them, and read any fork you generate from, before you trust it;
- the workflows and configuration the template puts into generated projects.

Out of scope: vulnerabilities in Copier itself (please report those to the Copier project), in an agent tool you use with a generated project, and in a project after you generated it, which is yours to maintain.

## Supported versions

Only the newest release tag receives fixes. Projects created from an older tag should run `copier update --trust` to move to the newest one.
