:lastproofread: 2026-01-23

.. _loopback-interface:

########
Loopback
########

The loopback interface is a virtual, software-based network interface. All 
traffic sent to it loops back and only targets services on the local host.

.. note:: Only one loopback ``lo`` interface is allowed per operating system. 
   If you require multiple virtual interfaces, use the :ref:`dummy-interface`
   interface type.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-address.txt
   :var0: loopback
   :var1: lo

.. cmdinclude:: /_include/interface-description.txt
   :var0: loopback
   :var1: lo

*********
Operation
*********

.. opcmd:: show interfaces loopback

   Show brief interface information.

   .. code-block:: none

     vyos@vyos:~$ show interfaces loopback
     Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
     Interface        IP Address                        S/L  Description
     ---------        ----------                        ---  -----------
     lo               127.0.0.1/8                       u/u
                      ::1/128

.. opcmd:: show interfaces loopback lo

   Show detailed interface information.

   .. code-block:: none

     vyos@vyos:~$ show interfaces loopback lo
     lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
         link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
         inet 127.0.0.1/8 scope host lo
            valid_lft forever preferred_lft forever
         inet6 ::1/128 scope host
            valid_lft forever preferred_lft forever

         RX:  bytes    packets     errors    dropped    overrun      mcast
                300          6          0          0          0          0
         TX:  bytes    packets     errors    dropped    carrier collisions
                300          6          0          0          0          0
