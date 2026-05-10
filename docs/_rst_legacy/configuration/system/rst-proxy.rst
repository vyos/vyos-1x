.. _system_proxy:

############
System Proxy
############

Some IT environments require the use of a proxy to connect to the Internet.
Without this configuration VyOS updates could not be installed directly by
using the :opcmd:`add system image` command (:ref:`update_vyos`).

.. cfgcmd:: set system proxy url <url>

   Set proxy for all connections initiated by VyOS, including HTTP, HTTPS, and
   FTP (anonymous ftp).

.. cfgcmd:: set system proxy port <port>

   Configure proxy port if it does not listen to the default port 80.

.. cfgcmd:: set system proxy username <username>

   Some proxys require/support the "basic" HTTP authentication scheme as per
   :rfc:`7617`, thus a username can be configured.

.. cfgcmd:: set system proxy password <password>

   Some proxys require/support the "basic" HTTP authentication scheme as per
   :rfc:`7617`, thus a password can be configured.
