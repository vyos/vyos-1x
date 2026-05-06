---
lastproofread: '2024-03-03'
---

(terraformvyos)=

# Terraform for VyOS

VyOS supports development infrastructure via Terraform and
provisioning via Ansible. Terraform allows you to automate the
process of deploying instances on many cloud and virtual
platforms. In this article, we will look at using Terraform to
deploy VyOS on platforms - AWS, Azure, and vSphere. For more
details about Terraform please have a look at [link].

You will need to [install] Terraform before proceeding.

Structure of files in the standard Terraform project:

```none
.
├── main.tf             # The main script
├── version.tf          # File for the changing version of Terraform.
├── variables.tf        # The file of all variables in "main.tf"
└── terraform.tfvars    # The value of all variables (passwords, login, IP addresses and so on)
```

General commands that we will use for running Terraform scripts

```none
cd /<your folder>       # go to the Terraform project
terraform init          # install all add-ons and providers (AWS, Azure, and so on)
terraform plan          # show what is changing
terraform apply         # run script
yes                     # apply running
```

% stop_vyoslinter

% start_vyoslinter

[install]: https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli
[link]: https://developer.hashicorp.com/terraform/intro

