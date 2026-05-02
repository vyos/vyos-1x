(index)=

# VyOS User Guide

::::::{grid} 3
:gutter: 2

:::::{grid-item-card} Get / Build VyOS

Quickly {ref}`Build<contributing/build-vyos:build vyos>`
your own Image or take a look at how to
{ref}`download<installation/install:download>`
a free or supported version.
:::::

:::::{grid-item-card} Install VyOS

Read about how to install VyOS on
{ref}`Bare Metal<installation/install:installation>`
or in a {ref}`VM <installation/virtual/index:Virtual Environments>`
and how to use an image with the usual
{ref}`cloud<installation/cloud/index:Cloud Environments>`
providers
:::::

:::::{grid-item-card} Configuration and Operation

Use the {ref}`Quickstart Guide<quick-start:Quick Start>`,
to have a fast overview. Or go deeper and set up
{ref}`advanced routing<configuration/protocols/index:protocols>`,
{ref}`VRFs<configuration/vrf/index:vrf>`, or
{ref}`VPNs<configuration/vpn/index:vpn>` for example.
:::::

:::::{grid-item-card} Automate

Integrate VyOS in your automation Workflow with
{ref}`Ansible<vyos-ansible>`,
have your own {ref}`local scripts<command-scripting>`,
or configure VyOS with the
{ref}`HTTPS-API<vyosapi>`.
:::::

:::::{grid-item-card} Examples

Get some inspiration from the
{ref}`Blueprints <configexamples/index:Configuration Blueprints>`
to build your infrastructure.
:::::

:::::{grid-item-card} Contribute and Community

There are many ways to contribute to the project.
Add missing parts or improve the
{ref}`Documentation<documentation:Write Documentation>`.

Discuss in [Slack](https://slack.vyos.io/)
or the [Forum](https://forum.vyos.io).

Or you can pick up a [Task](https://vyos.dev/)
and fix the
{ref}`code<contributing/development:development>`.
:::::
::::::

```{toctree}
:hidden: true
:maxdepth: 1

introducing/about
introducing/history
```

```{toctree}
:caption: First Steps
:hidden: true
:maxdepth: 2

installation/index
quick-start
cli
```

```{toctree}
:caption: Adminguide
:hidden: true
:maxdepth: 2

configuration/index
operation/index
automation/index
troubleshooting/index
configexamples/index
vpp/index
```

```{toctree}
:caption: Development
:hidden: true
:maxdepth: 2

contributing/index
```

```{toctree}
:caption: Misc
:hidden: true
:maxdepth: 2

documentation
coverage
copyright
```
