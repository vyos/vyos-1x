.. _index:

###############
VyOS User Guide
###############


.. grid:: 3
   :gutter: 2

   .. grid-item-card:: Get / Build VyOS


      Quickly :ref:`Build<contributing/build-vyos:build vyos>`
      your own Image or take a look at how to
      :ref:`download<installation/install:download>`
      a free or supported version.


   .. grid-item-card:: Install VyOS

      Read about how to install VyOS on
      :ref:`Bare Metal<installation/install:installation>`
      or in a :ref:`VM <installation/virtual/index:Virtual Environments>`
      and how to use an image with the usual
      :ref:`cloud<installation/cloud/index:Cloud Environments>`
      providers


   .. grid-item-card:: Configuration and Operation

      Use the :ref:`Quickstart Guide<quick-start:Quick Start>`,
      to have a fast overview. Or go deeper and set up
      :ref:`advanced routing<configuration/protocols/index:protocols>`,
      :ref:`VRFs<configuration/vrf/index:vrf>`, or
      :ref:`VPNs<configuration/vpn/index:vpn>` for example.


   .. grid-item-card:: Automate

      Integrate VyOS in your automation Workflow with
      :ref:`Ansible<vyos-ansible>`,
      have your own :ref:`local scripts<command-scripting>`,
      or configure VyOS with the
      :ref:`HTTPS-API<vyosapi>`.


   .. grid-item-card::  Examples

      Get some inspiration from the
      :ref:`Blueprints <configexamples/index:Configuration Blueprints>`
      to build your infrastructure.


   .. grid-item-card:: Contribute and Community

      | There are many ways to contribute to the project.
      | Add missing parts or improve the
        :ref:`Documentation<documentation:Write Documentation>`.
      | Discuss in `Slack <https://slack.vyos.io/>`_
        or the `Forum <https://forum.vyos.io>`_.
      | Or you can pick up a `Task <https://vyos.dev/>`_
        and fix the
        :ref:`code<contributing/development:development>`.


.. toctree::
   :hidden:
   :maxdepth: 1

   introducing/about
   introducing/history


.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: First Steps

   installation/index
   quick-start
   cli

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Adminguide


   configuration/index
   operation/index
   automation/index
   troubleshooting/index
   configexamples/index
   vpp/index


.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Development

   contributing/index


.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Misc

   documentation
   coverage
   copyright
