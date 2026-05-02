---
lastproofread: '2026-03-23'
---

# VyOS Terraform

VyOS supports development infrastructure via Terraform and provisioning
via Ansible.
Terraform allows you to automate the deployment of instances on a number of
cloud and virtual platforms. This section shows how to deploy VyOS on
multiple platforms: AWS, Microsoft Azure, Google Cloud Platform (GCP),
and VMware vSphere.
For more information, see the
official documentation for [Terraform] and [Ansible].

```{toctree}
:caption: Guides
:maxdepth: 1

terraformvyos
terraformAWS
terraformAZ
terraformGoogle
terraformvSphere
```

[ansible]: https://docs.ansible.com
[install]: https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli
[terraform]: https://developer.hashicorp.com/terraform/intro
