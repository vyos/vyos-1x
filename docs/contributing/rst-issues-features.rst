:lastproofread: 2025-12-08

.. _issues_features:

#######################
Issues/Feature requests
#######################

.. _bug_report:

Bug Report/Issue
================

Issues and bugs occur in every software project, and VyOS is no exception.

I found a bug, what should I do?
--------------------------------

When you find a potential bug, first: 

* Consult the documentation_ to ensure you configured your system
  correctly.
* Check if the VyOS community has identified a workaround for the bug through
  Slack_ or the VyOS Forum_.

Ensure the bug is reproducible
------------------------------

Include the following information when reporting a bug:

* A sequence of configuration commands or a complete configuration file needed
  to recreate the bug. Avoid partial configurations: a sequence of commands is
  easy to paste and a complete configuration is easy to load, but a partial
  config is hard to reconstruct.
* Describe the expected behavior and how it differs from what you observe.
  Include command outputs or traffic dumps. Explain briefly why these outputs
  are incorrect and what the correct behavior should be.
* A sequence of actions that trigger the bug. While not always possible, this
  helps developers and community members confirm the issue and verify fixes.
* If the bug is a regression, specify the VyOS version where the feature worked
  correctly (any working version is acceptable). Identify the exact version
  that the feature stopped working, if possible. 

If you are uncertain whether the behavior is a bug or what the correct behavior
is, or if you lack a reliable reproducing procedure, post on the forum or ask in
chat first. If you have a subscription, create a support ticket. The team and
community can help identify the issue, work around it, and create an actionable
bug report.

Report a Bug
------------

To open a bug report or feature request, create an account on
`vyos.dev <https://vyos.dev>`__, the public issue tracker for VyOS.

When creating a new issue, select the appropriate project and:

* Provide as much information as you can.
* Specify which VyOS version you are using: ``run show version``.
* Explain how to reproduce the bug.

.. _feature_request:

Feature Requests
================

Have an idea to improve VyOS or need a feature that would benefit all users?
Before submitting a feature request, search the public issue tracker
`vyos.dev <https://vyos.dev>`__ to check if a request already exists. You can
also enhance an existing request by providing additional information.

Create a task before starting work on a feature,
even if it is a trivial feature.
The task tracker generates release notes, so all work must be reflected
in the tracker.

Include at least the following information:

* Provide a detailed description of the feature: what it is, how it works, and
  how you would use it. Maintainers may not have experience with every feature,
  protocol, and tool in VyOS. Detailed information helps VyOS contributors and
  maintainers test new features they are unfamiliar with.
* Include proposed CLI syntax if the feature requires new commands. Provide both
  configuration and operational mode commands if both are needed.

Consider including the following information:

* Is the feature already supported by the underlying component
  (FreeRangeRouting, nftables, Kea, etc.)?
* How would you configure the feature manually within that component?
* Are there any limitations to using the feature
  (hardware support, resource usage)?
* Are there any adverse or non-obvious interactions with other features? Should
  the feature be mutually exclusive? 
* Any relevant documentation or references about the feature.

You do not need to provide all this information, but if you can, it simplifies
developers' work considerably. Research these questions when possible.

Task auto-closing
=================

A special task status exists for when all work by maintainers and contributors
is complete: **Needs reporter action**.

VyOS assigns this status to:

* Feature requests that do not include required information and need
  clarification.
* Bug reports that lack reproducing procedures.
* Tasks that are implemented and tested by the implementation author,
  but require testing in the real-world environment that only the reporter
  can replicate (for example, hardware VyOS does not support or specific
  network conditions).

When a task is set to **Needs reporter action**:

* If the reporter does not respond within two weeks, the task bot adds a comment
  ("Any news?") to remind the reporter.
* If there is still no response after another two weeks,
  the task is closed automatically.

We do not auto-close tasks with any other status and do not close tasks due to
lack of maintainer activity.

.. _documentation: https://docs.vyos.io
.. _Slack: https://slack.vyos.io
.. _Forum: https://forum.vyos.io

.. include:: /_include/common-references.txt
