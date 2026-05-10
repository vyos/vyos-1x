:lastproofread: 2026-02-02

.. _vyosonvmware:

Running on VMware ESXi
######################

ESXi 5.5 or later
*****************

``.ova`` files are available for supporting users. You can also set up VyOS
using a generic Linux instance by attaching the bootable ISO file and
installing using the ``install image`` command.

.. NOTE:: Previous issues have been documented with GRE/IPSEC tunneling
   using the E1000 adapter on VyOS guests. Use the VMXNET3 adapter instead.

Memory Contention Considerations
--------------------------------
When the underlying ESXi host reaches approximately 92% memory utilization,
it begins the balloon process to reclaim memory from guest operating systems.
This creates artificial memory pressure through the ``vmmemctl`` driver. Because
VyOS does not have a swap file by default, this pressure cannot move memory
data to a paging file. Instead, it consumes memory and forces the guest into
a low memory state with no recovery option. The balloon can expand to 65% of
guest allocated memory, so a VyOS guest using more than 35% of memory can
encounter an out-of-memory situation and trigger the kernel ``oom_kill`` 
process.  The ``oom_kill`` process then terminates memory-hungry processes.

To prevent ballooning, configure VyOS routers in a resource group with
adequate memory reservations.


References
----------

.. stop_vyoslinter

https://muralidba.blogspot.com/2018/03/how-does-linux-out-of-memory-oom-killer.html

.. start_vyoslinter