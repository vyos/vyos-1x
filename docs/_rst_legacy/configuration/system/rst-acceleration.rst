.. _acceleration:

############
Acceleration
############

In this command tree, all hardware acceleration options will be handled.
At the moment only `Intel® QAT`_ is supported

**********
Intel® QAT
**********

.. opcmd:: show system acceleration qat

    use this command to check if there is an Intel® QAT supported Processor in
    your system.

    .. code-block::

        vyos@vyos:~$ show system acceleration qat
        01:00.0 Co-processor [0b40]: Intel Corporation Atom Processor C3000 Series QuickAssist Technology [8086:19e2] (rev 11)

    if there is non device the command will show ```No QAT device found```

.. cfgcmd:: set system acceleration qat

    if there is a supported device, enable Intel® QAT

.. opcmd:: show system acceleration qat status

    Check if the Intel® QAT device is up and ready to do the job.

    .. code-block::

        vyos@vyos:~$ show system acceleration qat status
        Checking status of all devices.
        There is 1 QAT acceleration device(s) in the system:
        qat_dev0 - type: c3xxx,  inst_id: 0,  node_id: 0,  bsf: 0000:01:00.0,  #accel: 3 #engines: 6 state: up
    
Operation Mode
==============

.. opcmd:: show system acceleration qat device <device> config

    Show the full config uploaded to the QAT device.

.. opcmd:: show system acceleration qat device <device> flows

    Get an overview over the encryption counters.

.. opcmd:: show system acceleration qat interrupts

    Show binded qat device interrupts to certain core.


Example
=======

Let's build a simple VPN between 2 Intel® QAT ready devices.

Side A:

.. code-block::


    set interfaces vti vti1 address '192.168.1.2/24'
    set vpn ipsec authentication psk right id '10.10.10.2'
    set vpn ipsec authentication psk right id '10.10.10.1'
    set vpn ipsec authentication psk right secret 'Qwerty123'
    set vpn ipsec esp-group MyESPGroup proposal 1 encryption 'aes256'
    set vpn ipsec esp-group MyESPGroup proposal 1 hash 'sha256'
    set vpn ipsec ike-group MyIKEGroup proposal 1 dh-group '14'
    set vpn ipsec ike-group MyIKEGroup proposal 1 encryption 'aes256'
    set vpn ipsec ike-group MyIKEGroup proposal 1 hash 'sha256'
    set vpn ipsec interface 'eth0'
    set vpn ipsec site-to-site peer right authentication local-id '10.10.10.2'
    set vpn ipsec site-to-site peer right authentication mode 'pre-shared-secret'
    set vpn ipsec site-to-site peer right authentication remote-id '10.10.10.1'
    set vpn ipsec site-to-site peer right connection-type 'initiate'
    set vpn ipsec site-to-site peer right default-esp-group 'MyESPGroup'
    set vpn ipsec site-to-site peer right ike-group 'MyIKEGroup'
    set vpn ipsec site-to-site peer right local-address '10.10.10.2'
    set vpn ipsec site-to-site peer right remote-address '10.10.10.1'
    set vpn ipsec site-to-site peer right vti bind 'vti1'

Side B:

.. code-block::

    set interfaces vti vti1 address '192.168.1.1/24'
    set vpn ipsec authentication psk left id '10.10.10.2'
    set vpn ipsec authentication psk left id '10.10.10.1'
    set vpn ipsec authentication psk left secret 'Qwerty123'
    set vpn ipsec esp-group MyESPGroup proposal 1 encryption 'aes256'
    set vpn ipsec esp-group MyESPGroup proposal 1 hash 'sha256'
    set vpn ipsec ike-group MyIKEGroup proposal 1 dh-group '14'
    set vpn ipsec ike-group MyIKEGroup proposal 1 encryption 'aes256'
    set vpn ipsec ike-group MyIKEGroup proposal 1 hash 'sha256'
    set vpn ipsec interface 'eth0'
    set vpn ipsec site-to-site peer left authentication local-id '10.10.10.1'
    set vpn ipsec site-to-site peer left authentication mode 'pre-shared-secret'
    set vpn ipsec site-to-site peer left authentication remote-id '10.10.10.2'
    set vpn ipsec site-to-site peer left connection-type 'initiate'
    set vpn ipsec site-to-site peer left default-esp-group 'MyESPGroup'
    set vpn ipsec site-to-site peer left ike-group 'MyIKEGroup'
    set vpn ipsec site-to-site peer left local-address '10.10.10.1'
    set vpn ipsec site-to-site peer left remote-address '10.10.10.2'
    set vpn ipsec site-to-site peer left vti bind 'vti1'

a bandwidth test over the VPN got these results:

.. code-block::

    Connecting to host 192.168.1.2, port 5201
    [  9] local 192.168.1.1 port 51344 connected to 192.168.1.2 port 5201
    [ ID] Interval           Transfer     Bitrate         Retr  Cwnd
    [  9]   0.00-1.01   sec  32.3 MBytes   268 Mbits/sec    0    196 KBytes
    [  9]   1.01-2.03   sec  32.5 MBytes   268 Mbits/sec    0    208 KBytes
    [  9]   2.03-3.03   sec  32.5 MBytes   271 Mbits/sec    0    208 KBytes
    [  9]   3.03-4.04   sec  32.5 MBytes   272 Mbits/sec    0    208 KBytes
    [  9]   4.04-5.00   sec  31.2 MBytes   272 Mbits/sec    0    208 KBytes
    [  9]   5.00-6.01   sec  32.5 MBytes   272 Mbits/sec    0    234 KBytes
    [  9]   6.01-7.04   sec  32.5 MBytes   265 Mbits/sec    0    234 KBytes
    [  9]   7.04-8.04   sec  32.5 MBytes   272 Mbits/sec    0    234 KBytes
    [  9]   8.04-9.04   sec  32.5 MBytes   273 Mbits/sec    0    336 KBytes
    [  9]   9.04-10.00  sec  31.2 MBytes   272 Mbits/sec    0    336 KBytes
    - - - - - - - - - - - - - - - - - - - - - - - - -
    [ ID] Interval           Transfer     Bitrate         Retr
    [  9]   0.00-10.00  sec   322 MBytes   270 Mbits/sec    0           sender
    [  9]   0.00-10.00  sec   322 MBytes   270 Mbits/sec                receiver

with :cfgcmd:`set system acceleration qat` on both systems the bandwidth
increases.

.. code-block::

    Connecting to host 192.168.1.2, port 5201
    [  9] local 192.168.1.1 port 51340 connected to 192.168.1.2 port 5201
    [ ID] Interval           Transfer     Bitrate         Retr  Cwnd
    [  9]   0.00-1.00   sec  97.3 MBytes   817 Mbits/sec    0   1000 KBytes
    [  9]   1.00-2.00   sec  92.5 MBytes   776 Mbits/sec    0   1.07 MBytes
    [  9]   2.00-3.00   sec  92.5 MBytes   776 Mbits/sec    0    820 KBytes
    [  9]   3.00-4.00   sec  92.5 MBytes   776 Mbits/sec    0    899 KBytes
    [  9]   4.00-5.00   sec  91.2 MBytes   765 Mbits/sec    0    972 KBytes
    [  9]   5.00-6.00   sec  92.5 MBytes   776 Mbits/sec    0   1.02 MBytes
    [  9]   6.00-7.00   sec  92.5 MBytes   776 Mbits/sec    0   1.08 MBytes
    [  9]   7.00-8.00   sec  92.5 MBytes   776 Mbits/sec    0   1.14 MBytes
    [  9]   8.00-9.00   sec  91.2 MBytes   765 Mbits/sec    0    915 KBytes
    [  9]   9.00-10.00  sec  92.5 MBytes   776 Mbits/sec    0   1000 KBytes
    - - - - - - - - - - - - - - - - - - - - - - - - -
    [ ID] Interval           Transfer     Bitrate         Retr
    [  9]   0.00-10.00  sec   927 MBytes   778 Mbits/sec    0             sender
    [  9]   0.00-10.01  sec   925 MBytes   775 Mbits/sec                  receiver


.. _`Intel® QAT`: https://www.intel.com/content/www/us/en/architecture-and-technology/intel-quick-assist-technology-overview.html
