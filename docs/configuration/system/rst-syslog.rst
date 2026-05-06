.. _syslog:

######
Syslog
######

Overview
========

By default, VyOS provides a minimal logging configuration with local storage 
and log rotation. All errors, including local7 messages, are saved to a local 
file. Emergency alerts are sent to the console.

To change these settings, enter configuration mode.

Syslog configuration
====================

Syslog supports logging to multiple destinations: a local file, a console, or 
a remote syslog server over UDP or TCP.

The syslog configuration is organized into the following categories:

* Global settings
* Local logging  
* Console logging
* Remote logging
* TLS-encrypted remote logging

Global settings
---------------
Configure the general behavior of the syslog service.

.. cfgcmd:: set system syslog marker interval <number>

   **Configure the interval, in seconds, for sending syslog mark messages.**

   Syslog mark messages confirm the logging service is operational.

   Default: 1200 seconds.

.. cfgcmd:: set system syslog marker disable

   Disable sending syslog mark messages.

.. cfgcmd:: set system syslog preserve-fqdn

   **Configure how the logging device's hostname appears in log messages sent 
   to a remote syslog server.**

   If configured, the device includes its :abbr:`FQDN (Fully Qualified Domain 
   Name)` in log messages, even if the syslog server is in the same domain.


Local logging
-------------

Configure which log messages to save to a local log file.

.. cfgcmd:: set system syslog local <filename> facility <keyword> level <keyword>

   **Configure syslog to save log messages for a specific facility and 
   severity level to ``/var/log/messages``.**
   
   Refer to the tables below for valid facility and severity options.

.. _syslog_console:

Console logging
---------------

Configure which log messages to send to ``/dev/console``.

.. cfgcmd:: set system syslog console facility <keyword> level <keyword>

   **Configure syslog to send log messages for a specific facility and severity 
   level to the device's console.**

   Refer to the tables below for valid facility and severity options.

.. _syslog_remote:

Remote logging
--------------

Configure **remote logging** to send log messages to a remote syslog server.

Remote logging does not affect either **local** or **console logging** and 
runs in parallel with them. Remote logging supports sending log messages 
to multiple hosts. 

.. cfgcmd:: set system syslog remote <address> facility <keyword> level <keyword>

   **Configure log transmission to the remote syslog server for a specific 
   facility and severity level.**

   The server’s address can be specified using either a :abbr:`FQDN (Fully 
   Qualified Domain Name)` or an IP address.

   Refer to the tables below for valid facility and severity options.

.. cfgcmd:: set system syslog remote <address> protocol <udp | tcp>

   **Configure the protocol for log transmission.** 

   The protocol can be either UDP or TCP. By default, log messages are sent 
   over UDP.

.. cfgcmd:: set system syslog remote <address> port <port>

   **Configure the port for log transmission.**

   By default, the standard port 514 is used.

.. cfgcmd:: set system syslog remote <address> format include-timezone

   **Configure log transmission in the RFC 5424 format.**

   The RFC 5424 format includes the timezone in the timestamp. For example: 

   .. code-block:: none

      <34>1 2003-10-11T22:14:15.003-07:00 mymachine.example.com su - ID47 - BOM’su root’ failed for lonvick on /dev/pts/8.
  
   By default, log messages are sent in the RFC 3164 format. For example: 

   .. code-block:: none

      <34>Oct 11 22:14:15 mymachine su: ‘su root’ failed for lonvick on /dev/pts/8

.. cfgcmd:: set system syslog remote <address> format octet-counted

   **Enable octet-counted framing for log transmission.** 

   When enabled, multi-line log messages are sent without splitting. Ensure 
   the remote server supports octet-counted framing to avoid parsing errors.

   Octet-counted framing is not available for the UDP protocol.

.. cfgcmd:: set system syslog remote <address> vrf <name>

   Configure the :abbr:`VRF (Virtual Routing and Forwarding)` instance
   for log transmission.

.. cfgcmd:: set system syslog remote <address> source-address <address>

   Configure the source IP address (IPv4 or IPv6) for log transmission.

:abbr:`TLS (Transport Layer Security)`-encrypted remote logging
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

VyOS supports :abbr:`TLS (Transport Layer Security)`-encrypted remote logging 
over TCP to ensure secure transmission of syslog data to remote syslog servers.

**Prerequisites**: Before configuring :abbr:`TLS (Transport Layer 
Security)`-encrypted remote logging, ensure you have: 

* A valid remote syslog server address.
* Valid :abbr:`CA (Certificate Authority)` and client certificates uploaded 
  to the local :abbr:`PKI (Public Key Infrastructure)` storage.
* The **remote syslog transport protocol** is set to **TCP**: 

  .. code-block:: none

     set system syslog remote <address> protocol tcp


.. note:: :abbr:`TLS (Transport Layer Security)`-encrypted remote logging is 
   **not supported** over **UDP**.

.. cfgcmd:: set system syslog remote <address> tls

   Enable TLS-encrypted remote logging.
 
.. cfgcmd:: set system syslog remote <address> tls ca-certificate <ca_name>

   **Configure the** :abbr:`CA (Certificate Authority)` **certificate.**

   The syslog client uses the :abbr:`CA (Certificate Authority)` certificate to 
   verify the identity of the remote syslog server.

   The :abbr:`CA (Certificate Authority)` certificate is required for **all** 
   authentication modes except ``anon``.

.. cfgcmd:: set system syslog remote <address> tls certificate <cert_name>
 
   **Configure the client certificate.**

   The remote syslog server uses the client certificate to verify the identity 
   of the syslog client.

   The client certificate is required if the remote syslog server enforces 
   client certificate verification.

.. cfgcmd:: set system syslog remote <address> tls auth-mode <anon | fingerprint
   | certvalid | name>

   **Configure the authentication mode.**

   The authentication mode defines how the syslog client verifies the syslog 
   server's identity.

   The following authentication modes are available:

   * ``anon`` **(default)**: Allows encrypted connections without verifying the syslog 
     server's identity. This mode is **not recommended**, as it is vulnerable to 
     :abbr:`MITM (Man-in-the-Middle)` attacks. 
   * ``fingerprint``: Verifies the server’s certificate fingerprint against the 
     value preconfigured with:

     .. code-block:: none

        set system syslog remote <address> tls permitted-peer <peer>
               
   * ``certvalid``: Verifies the server certificate is signed by a trusted 
     :abbr:`CA (Certificate Authority)`, skipping :abbr:`CN (Common Name)` check.
   * ``name``: Verifies that:

     * The server’s certificate is signed by a trusted :abbr:`CA (Certificate 
       Authority)`.
     * The :abbr:`CN (Common Name)` in the certificate matches the value 
       preconfigured with: 

     .. code-block:: none

        set system syslog remote <address> tls permitted-peer <peer>

     This is a **recommended** secure mode for production environments.

.. cfgcmd:: set system syslog remote <address> tls permitted-peer <peer>

   **Configure the peer certificate identifiers.**

   The certificate identifier format depends on the authentication mode:

   * ``fingerprint``: Enter the expected certificate fingerprints (SHA-1 or 
     SHA-256).
   * ``name``: Enter the expected certificate :abbr:`CNs (Common Names)`.
   
   For ``anon`` and ``certvalid`` authentication modes, certificate identifiers 
   are not required.

Examples:
^^^^^^^^^

.. code-block:: none

   # Example of 'anon' authentication mode
   set system syslog remote 10.10.2.3 facility all level debug
   set system syslog remote 10.10.2.3 port 6514
   set system syslog remote 10.10.2.3 protocol tcp
   set system syslog remote 10.10.2.3 tls auth-mode anon
   # or just use 'set system syslog remote 10.10.2.3 tls'

   # Example of 'certvalid' authentication mode
   set system syslog remote elk.example.com facility all level debug
   set system syslog remote elk.example.com port 6514
   set system syslog remote elk.example.com protocol tcp
   set system syslog remote elk.example.com tls ca-certificate my-ca
   set system syslog remote elk.example.com tls auth-mode certvalid

   # Example of 'fingerprint' authentication mode
   set system syslog remote syslog.example.com facility all level debug
   set system syslog remote syslog.example.com port 6514
   set system syslog remote syslog.example.com protocol tcp
   set system syslog remote syslog.example.com tls ca-certificate my-ca
   set system syslog remote syslog.example.com tls auth-mode fingerprint
   set system syslog remote syslog.example.com tls permitted-peers 'SHA1:10:C4:26:...,SHA256:7B:4B:10:...'

   # Example of 'name' authentication mode
   set system syslog remote graylog.example.com facility all level debug
   set system syslog remote graylog.example.com port 6514
   set system syslog remote graylog.example.com protocol tcp
   set system syslog remote graylog.example.com tls ca-certificate my-ca
   set system syslog remote graylog.example.com tls certificate syslog-client
   set system syslog remote graylog.example.com tls auth-mode name
   set system syslog remote graylog.example.com tls permitted-peers 'graylog.example.com'

Security recommendations
^^^^^^^^^^^^^^^^^^^^^^^^

* For secure deployments, always use the ``name`` authentication mode. It 
  ensures that the server is validated by a trusted :abbr:`CA (Certificate 
  Authority)` and that the hostname matches the certificate.
* Use the ``anon`` authentication mode only in testing environments, as it 
  doesn't provide  server authentication.
* Ensure private keys are generated, stored, and maintained exclusively within 
  the :doc:`PKI system </configuration/pki/index>`.

.. _syslog_facilities:

Syslog facilities
=================

This section lists facilities used by syslog. Most facility names are self-
explanatory. The local0–local7 facilities are used for custom purposes, such as 
logging from network nodes and equipment. Facility assignment is flexible and 
should be tailored to your company's needs. Consider facilities as categorization 
tools, rather than strict directives.

+----------+----------+----------------------------------------------------+
| Facility | Keyword  | Description                                        |
| code     |          |                                                    |
+==========+==========+====================================================+
|          | all      | All facilities                                     |
+----------+----------+----------------------------------------------------+
| 0        | kern     | Kernel messages                                    |
+----------+----------+----------------------------------------------------+
| 1        | user     | User-level messages                                |
+----------+----------+----------------------------------------------------+
| 2        | mail     | Mail system                                        |
+----------+----------+----------------------------------------------------+
| 3        | daemon   | System daemons                                     |
+----------+----------+----------------------------------------------------+
| 4        | auth     | Security/authentication messages                   |
+----------+----------+----------------------------------------------------+
| 5        | syslog   | Messages generated internally by syslog            |
+----------+----------+----------------------------------------------------+
| 6        | lpr      | Line printer subsystem                             |
+----------+----------+----------------------------------------------------+
| 7        | news     | Network news subsystem                             |
+----------+----------+----------------------------------------------------+
| 8        | uucp     | UUCP subsystem                                     |
+----------+----------+----------------------------------------------------+
| 9        | cron     | Clock daemon                                       |
+----------+----------+----------------------------------------------------+
| 10       | security | Security/authentication messages                   |
+----------+----------+----------------------------------------------------+
| 11       | ftp      | FTP daemon                                         |
+----------+----------+----------------------------------------------------+
| 12       | ntp      | NTP subsystem                                      |
+----------+----------+----------------------------------------------------+
| 13       | logaudit | Log audit                                          |
+----------+----------+----------------------------------------------------+
| 14       | logalert | Log alert                                          |
+----------+----------+----------------------------------------------------+
| 15       | clock    | clock daemon (note 2)                              |
+----------+----------+----------------------------------------------------+
| 16       | local0   | local use 0 (local0)                               |
+----------+----------+----------------------------------------------------+
| 17       | local1   | local use 1 (local1)                               |
+----------+----------+----------------------------------------------------+
| 18       | local2   | local use 2 (local2)                               |
+----------+----------+----------------------------------------------------+
| 19       | local3   | local use 3 (local3)                               |
+----------+----------+----------------------------------------------------+
| 20       | local4   | local use 4 (local4)                               |
+----------+----------+----------------------------------------------------+
| 21       | local5   | local use 5 (local5)                               |
+----------+----------+----------------------------------------------------+
| 22       | local6   | local use 6 (local6)                               |
+----------+----------+----------------------------------------------------+
| 23       | local7   | local use 7 (local7)                               |
+----------+----------+----------------------------------------------------+

.. _syslog_severity_level:

Severity levels
===============

+-------+---------------+---------+-------------------------------------------+
| Value | Severity      | Keyword | Description                               |
+=======+===============+=========+===========================================+
|       |               | all     | Log everything.                           |
+-------+---------------+---------+-------------------------------------------+
| 0     | Emergency     | emerg   | System is unusable - a panic condition.   |
+-------+---------------+---------+-------------------------------------------+
| 1     | Alert         | alert   | Action must be taken immediately - A      |
|       |               |         | condition that should be corrected        |
|       |               |         | immediately, such as a corrupted system   |
|       |               |         | database.                                 |
+-------+---------------+---------+-------------------------------------------+
| 2     | Critical      | crit    | Critical conditions - e.g., hard drive    |
|       |               |         | errors.                                   |
+-------+---------------+---------+-------------------------------------------+
| 3     | Error         | err     | Error conditions.                         |
+-------+---------------+---------+-------------------------------------------+
| 4     | Warning       | warning | Warning conditions.                       |
+-------+---------------+---------+-------------------------------------------+
| 5     | Notice        | notice  | Normal but significant conditions -       |
|       |               |         | conditions that are not error conditions, |
|       |               |         | but that may require special handling.    |
+-------+---------------+---------+-------------------------------------------+
| 6     | Informational | info    | Informational messages.                   |
+-------+---------------+---------+-------------------------------------------+
| 7     | Debug         | debug   | Debug-level messages - Messages that      |
|       |               |         | contain information normally of use only  |
|       |               |         | when debugging a program.                 |
+-------+---------------+---------+-------------------------------------------+


Display logs
============

.. opcmd:: show log [all | authorization | cluster | conntrack-sync | ...]

   **Display logs for a specific category on the console.**

   Use tab completion to view a list of available categories. 

   If no category is specified, all logs are shown.

.. opcmd:: show log image <name>
   [all | authorization | directory | file <file name> | tail <lines>]

   **Display logs for a specific image on the console.**

   Available log categories: 

   .. list-table::
      :widths: 25 75
      :header-rows: 0

      * - all
        - Displays the contents of system log files of the specified image.
      * - authorization
        - Displays authorization attempts of the specified image.
      * - directory
        - Displays user-defined log files of the specified image.
      * - file <file name>
        - Displays the contents of a specified user-defined log file of the specified
          image.
      * - tail
        - Displays last lines of the system log of the specified image.
      * - <lines>
        - Number of lines to be displayed, default 10.

If no category is specified, the contents of the main syslog file are
displayed.

.. hint:: Use ``show log | strip-private`` to hide private data
   when displaying your logs.
