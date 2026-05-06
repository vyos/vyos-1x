---
lastproofread: '2026-02-23'
---

(vpp-config-dataplane-index)=

```{include} /_include/need_improvement.txt
```

# VPP Dataplane Core Configuration

This section covers the core configuration options for the VPP dataplane in
VyOS. It includes settings for memory management, CPU allocation, hugepages,
and other essential parameters that influence the performance and behavior
of the VPP dataplane.

Please review the general system configuration, before starting to configure
VPP. Without proper VyOS preconditions, VPP will not start or its efficiency
will be significantly degraded.

```{toctree}
:includehidden: true
:maxdepth: 1

system
buffers
cpu
interface
ipsec
ipv6
l2learn
lcp
logging
memory
unix
```
