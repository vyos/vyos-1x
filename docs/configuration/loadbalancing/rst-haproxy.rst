:lastproofread: 2026-04-06

#############
HAproxy
#############

.. include:: /_include/need_improvement.txt

HAProxy is a load balancer and proxy server that provides
high-availability, load balancing, and proxying for TCP (level 4) and
HTTP-based (level 7) applications.

Configuration
=============


Service configuration specifies the port to bind to. Backend
configuration defines the load balancing method and specifies the backend
servers.

Service
-------

.. cfgcmd:: set load-balancing haproxy service <name> listen-address
   <address>

  Set the IP address for the service to bind to. By default, the service
  listens on all IPv4 and IPv6 addresses.

.. cfgcmd:: set load-balancing haproxy service <name> port
   <port>

  Create service `<name>` to listen on <port>

.. cfgcmd:: set load-balancing haproxy service <name> mode
   <tcp|http>

  Configure service `<name>` mode TCP or HTTP

.. cfgcmd:: set load-balancing haproxy service <name> backend
   <name>

  Configure service `<name>` to use the backend <name>

.. cfgcmd:: set load-balancing haproxy service <name> ssl
   certificate <name>

  Set the SSL certificate <name> for service <name>. You can define
  multiple certificates.

.. cfgcmd:: set load-balancing haproxy service <name>
  http-response-headers <header-name> value <header-value>

  Set custom HTTP headers to include in all responses.

.. cfgcmd:: set load-balancing haproxy service <name> logging facility
  <facility> level <level>

  Specify facility and level for logging.
  For an explanation on :ref:`syslog_facilities` and
  :ref:`syslog_severity_level`,
  see tables in the syslog configuration section.

.. cfgcmd:: set load-balancing haproxy service <name> timeout client
  <seconds>

  Set the maximum inactivity time on the client side for this service.
  Value range 1-3600 seconds.

.. cfgcmd:: set load-balancing haproxy service <name> http-compression algorithm
  <gzip | deflate | identity | raw-deflate>

  Set the compression algorithm to be used when compressing HTTP responses.

.. cfgcmd:: set load-balancing haproxy service <name> http-compression mime-type
  <mime-type>

  Set the list of HTTP response MIME types which haproxy will attempt to
  compress, if received uncompressed from backend server.

Rules
^^^^^
Rules control and route incoming traffic to specific backends based on
predefined conditions. Rules define matching criteria and specify actions
to perform.

.. cfgcmd:: set load-balancing haproxy service <name> rule <rule>
   domain-name <name>

  Match domain name

.. cfgcmd:: set load-balancing haproxy service <name> rule <rule>
   ssl <sni>

  SSL match Server Name Indication (SNI) option:
   * ``req-ssl-sni`` SSL Server Name Indication (SNI) request match
   * ``ssl-fc-sni`` SSL frontend connection Server Name Indication match
   * ``ssl-fc-sni-end`` SSL frontend match end of connection Server Name 
      
      Indication

.. cfgcmd:: set load-balancing haproxy service <name> rule <rule>
   url-path <match> <url>

  Define URL path matching rules for a specific service. Use this command
  to specify how to match the URL path against incoming requests.

  The available options for <match> are:
   * ``begin`` Matches the beginning of the URL path
   * ``end`` Matches the end of the URL path.
   * ``exact`` Matches the URL path exactly.

.. cfgcmd:: set load-balancing haproxy service <name> rule <rule>
   set backend <name>

  Assign a specific backend to a rule

.. cfgcmd:: set load-balancing haproxy service <name> rule <rule>
   redirect-location <url>

  Redirect URL to a new location.


Backend
-------

.. cfgcmd:: set load-balancing haproxy backend <name> balance
   <balance>

  Specify the load balancing algorithm for distributing requests among
  available servers.

  Balance algorithms:
   * ``source-address`` Distributes requests based on the source IP address
     of the client.
   * ``round-robin`` Distributes requests in a circular manner,
     sequentially sending each request to the next server in line.
   * ``least-connection`` Distributes requests to the server with the fewest
     active connections.

.. cfgcmd:: set load-balancing haproxy backend <name> mode
   <mode>

  Configure backend `<name>` mode TCP or HTTP.

.. cfgcmd:: set load-balancing haproxy backend <name> server
   <name> address <x.x.x.x>

  Set the address of the backend server that receives incoming traffic.

.. cfgcmd:: set load-balancing haproxy backend <name> server
   <name> port <port>

  Set the address of the backend port.

.. cfgcmd:: set load-balancing haproxy backend <name> server
   <name> check

  Active health check backend server.

.. cfgcmd:: set load-balancing haproxy backend <name> server
   <name> check port <port>

  Set an alternative port number for health checks.
  Overrides the default server port used for TCP/HTTP checks.

.. cfgcmd:: set load-balancing haproxy backend <name> server
   <name> send-proxy

  Send a Proxy Protocol version 1 header (text format).

.. cfgcmd:: set load-balancing haproxy backend <name> server
   <name> send-proxy-v2

  Send a Proxy Protocol version 2 header (binary format).

.. cfgcmd:: set load-balancing haproxy backend <name> ssl
   ca-certificate <ca-certificate>

  Use SSL encryption for backend requests and authenticate the backend
  against ``<ca-certificate>``.

.. cfgcmd:: set load-balancing haproxy backend <name> ssl no-verify

  Use SSL encryption for backend requests without validating the server
  certificate.

.. cfgcmd:: set load-balancing haproxy backend <name>
  http-response-headers <header-name> value <header-value>

  Set custom HTTP headers to include in all responses from the backend.

.. cfgcmd:: set load-balancing haproxy backend <name> logging facility
  <facility> level <level>

  Specify facility and level for logging.
  For an explanation on :ref:`syslog_facilities` and
  :ref:`syslog_severity_level`,
  see tables in the :ref:`syslog` configuration section.

.. cfgcmd:: set load-balancing haproxy backend <name> timeout check
  <seconds>

  Set the timeout in seconds for established connections.
  Value range 1-3600 seconds.


.. cfgcmd:: set load-balancing haproxy backend <name> timeout connect
  <seconds>

  Set the maximum time to wait for a connection attempt to a server to succeed.
  Value range 1-3600 seconds.

.. cfgcmd:: set load-balancing haproxy backend <name> timeout server
  <seconds>

  Set the maximum inactivity time on the server side.
  Value range 1-3600 seconds.



Global
-------

Global configuration parameters:

.. cfgcmd:: set load-balancing haproxy global-parameters max-connections
   <num>

  Limit maximum number of connections

.. cfgcmd:: set load-balancing haproxy global-parameters ssl-bind-ciphers
   <ciphers>

  Limit the cipher algorithms allowed during SSL/TLS handshake.

.. cfgcmd:: set load-balancing haproxy global-parameters tls-version-min
   <version>

  Specify the minimum required TLS version 1.2 or 1.3

.. cfgcmd:: set load-balancing haproxy global-parameters logging
  facility <facility> level <level>

  Specify facility and level for logging.
  For an explanation on :ref:`syslog_facilities` and
  :ref:`syslog_severity_level`
  see tables in syslog configuration section.

.. cfgcmd:: set load-balancing haproxy timeout check <seconds>

  Set the timeout in seconds for established connections.
  Value range 1-3600 seconds. Default is 5 seconds.

.. cfgcmd:: set load-balancing haproxy timeout client <seconds>

  Set the maximum inactivity time on the client side.
  Value range 1-3600 seconds. Default is 50 seconds.

.. cfgcmd:: set load-balancing haproxy timeout connect <seconds>

  Set the maximum time to wait for a connection attempt to a server to succeed.
  Value range 1-3600 seconds. Default is 10 seconds.

.. cfgcmd:: set load-balancing haproxy timeout server <seconds>

  Set the maximum inactivity time on the server side.
  Value range 1-3600 seconds. Default is 50 seconds.

Health checks
=============


HTTP checks
-----------

Use HTTP health checks to monitor web applications that provide health status
information and determine their availability.

.. cfgcmd:: set load-balancing haproxy backend <name> http-check

  Enables HTTP health checks using OPTION HTTP requests against '/' and
  expecting a successful response code in the 200-399 range.

.. cfgcmd:: set load-balancing haproxy backend <name> http-check
   method <method>

  Set the HTTP method: ``OPTION``, ``GET``, ``POST``, or ``PUT``.

.. cfgcmd:: set load-balancing haproxy backend <name> http-check
   uri <path>

  Set the endpoint to use for health checks.

.. cfgcmd:: set load-balancing haproxy backend <name> http-check
   expect <condition>

  Set the expected result condition for a server to be considered healthy.

  Some possible examples are:
   * ``status 200`` Expecting a 200 response code
   * ``status 200-399`` Expecting a non-failure response code
   * ``string success`` Expecting the string `success` in the response body


TCP checks
----------

Configure health checks for TCP mode backends. You can configure protocol-aware
checks for a range of Layer 7 protocols:

.. cfgcmd:: set load-balancing haproxy backend <name> health-check <protocol>

  Available health check protocols:
   * ``ldap`` LDAP protocol check.
   * ``redis`` Redis protocol check.
   * ``mysql`` MySQL protocol check.
   * ``pgsql`` PostgreSQL protocol check.
   * ``smtp`` SMTP protocol check.

.. note:: If you specify a server to check but do not configure a
   protocol, HAProxy performs a basic TCP health check. A server is online if
   it responds to a connection attempt with a valid ``SYN/ACK`` packet.


Redirect HTTP to HTTPS
======================

Configure a HAProxy service for HTTP that listens on port 80 and redirects
incoming requests to HTTPS:

.. code-block:: none

    set load-balancing haproxy service http port '80'
    set load-balancing haproxy service http redirect-http-to-https

You can use a different service name; in this example, ``http`` is just for
convenience.


Examples
========

Level 4 balancing
-----------------

This configuration enables the TCP reverse proxy for the ``my-tcp-api``
service. Incoming TCP connections on port 8888 are load balanced across the
backend servers (srv01 and srv02) using the round-robin load balancing
algorithm.

.. code-block:: none

    set load-balancing haproxy service my-tcp-api backend 'bk-01'
    set load-balancing haproxy service my-tcp-api mode 'tcp'
    set load-balancing haproxy service my-tcp-api port '8888'

    set load-balancing haproxy backend bk-01 balance 'round-robin'
    set load-balancing haproxy backend bk-01 mode 'tcp'

    set load-balancing haproxy backend bk-01 server srv01 address '192.0.2.11'
    set load-balancing haproxy backend bk-01 server srv01 port '8881'
    set load-balancing haproxy backend bk-01 server srv02 address '192.0.2.12'
    set load-balancing haproxy backend bk-01 server srv02 port '8882'


Balancing based on domain name
------------------------------
The following configuration demonstrates how to use VyOS
to achieve load balancing based on the domain name:

The HTTP service listens on TCP port 80.

Rule 10 matches requests with the domain name ``node1.example.com`` and
forwards them to the backend ``bk-api-01``.

Rule 20 matches requests with the domain name ``node2.example.com`` and
forwards them to the backend ``bk-api-02``.

.. code-block:: none

    set load-balancing haproxy service http description 'bind app listen on 443 port'
    set load-balancing haproxy service http mode 'tcp'
    set load-balancing haproxy service http port '80'

    set load-balancing haproxy service http rule 10 domain-name 'node1.example.com'
    set load-balancing haproxy service http rule 10 set backend 'bk-api-01'
    set load-balancing haproxy service http rule 20 domain-name 'node2.example.com'
    set load-balancing haproxy service http rule 20 set backend 'bk-api-02'

    set load-balancing haproxy backend bk-api-01 description 'My API-1'
    set load-balancing haproxy backend bk-api-01 mode 'tcp'
    set load-balancing haproxy backend bk-api-01 server api01 address '127.0.0.1'
    set load-balancing haproxy backend bk-api-01 server api01 port '4431'
    set load-balancing haproxy backend bk-api-02 description 'My API-2'
    set load-balancing haproxy backend bk-api-02 mode 'tcp'
    set load-balancing haproxy backend bk-api-02 server api01 address '127.0.0.2'
    set load-balancing haproxy backend bk-api-02 server api01 port '4432'


Terminate SSL
-------------

The following configuration terminates SSL on the router.

The ``http`` service listens on port 80 and redirects HTTP requests to
HTTPS.

The ``https`` service listens on port 443 with the ``bk-default`` backend
and handles HTTPS traffic using the ``cert`` certificate for SSL termination.
The HSTS header is set with a 1-year expiry to tell browsers to always use
SSL for the site.

Rule 10 matches requests with the exact URL path ``/.well-known/xxx`` and
redirects them to ``/certs/``.

Rule 20 matches requests with URL paths ending in ``/mail`` or the exact
path ``/email/bar`` and redirects them to ``/postfix/``.

Global parameters include a maximum connection limit of 4000 and a minimum
TLS version of 1.3.


.. code-block:: none

    set load-balancing haproxy service http description 'Force redirect to HTTPS'
    set load-balancing haproxy service http port '80'
    set load-balancing haproxy service http redirect-http-to-https

    set load-balancing haproxy service https backend 'bk-default'
    set load-balancing haproxy service https description 'listen on 443 port'
    set load-balancing haproxy service https mode 'http'
    set load-balancing haproxy service https port '443'
    set load-balancing haproxy service https ssl certificate 'cert'
    set load-balancing haproxy service https http-response-headers Strict-Transport-Security value 'max-age=31536000'

    set load-balancing haproxy service https rule 10 url-path exact '/.well-known/xxx'
    set load-balancing haproxy service https rule 10 set redirect-location '/certs/'
    set load-balancing haproxy service https rule 20 url-path end '/mail'
    set load-balancing haproxy service https rule 20 url-path exact '/email/bar'
    set load-balancing haproxy service https rule 20 set redirect-location '/postfix/'

    set load-balancing haproxy backend bk-default description 'Default backend'
    set load-balancing haproxy backend bk-default mode 'http'
    set load-balancing haproxy backend bk-default server sr01 address '192.0.2.23'
    set load-balancing haproxy backend bk-default server sr01 port '80'

    set load-balancing haproxy global-parameters max-connections '4000'
    set load-balancing haproxy global-parameters tls-version-min '1.3'


SSL Bridging
-------------

The following configuration terminates incoming HTTPS traffic on the router,
then re-encrypts the traffic and sends it to the backend server via HTTPS.
Use this when encryption is required for both paths but you do not want to
install publicly trusted certificates on each backend server.

Backend service certificates are checked against the certificate authority
specified in the configuration, which could be an internal CA.

The ``https`` service listens on port 443 with backend ``bk-bridge-ssl`` to
handle HTTPS traffic. It uses certificate named ``cert`` for SSL termination.

The ``bk-bridge-ssl`` backend connects to ``sr01`` server on port 443 via HTTPS
and checks backend server has a valid certificate trusted by CA ``cacert``


.. code-block:: none

    set load-balancing haproxy service https backend 'bk-bridge-ssl'
    set load-balancing haproxy service https description 'listen on 443 port'
    set load-balancing haproxy service https mode 'http'
    set load-balancing haproxy service https port '443'
    set load-balancing haproxy service https ssl certificate 'cert'

    set load-balancing haproxy backend bk-bridge-ssl description 'SSL backend'
    set load-balancing haproxy backend bk-bridge-ssl mode 'http'
    set load-balancing haproxy backend bk-bridge-ssl ssl ca-certificate 'cacert'
    set load-balancing haproxy backend bk-bridge-ssl server sr01 address '192.0.2.23'
    set load-balancing haproxy backend bk-bridge-ssl server sr01 port '443'


Balancing with HTTP health checks
---------------------------------

This configuration enables HTTP health checks for backend servers.

.. code-block:: none

    set load-balancing haproxy service my-tcp-api backend 'bk-01'
    set load-balancing haproxy service my-tcp-api mode 'tcp'
    set load-balancing haproxy service my-tcp-api port '8888'

    set load-balancing haproxy backend bk-01 balance 'round-robin'
    set load-balancing haproxy backend bk-01 mode 'tcp'

    set load-balancing haproxy backend bk-01 http-check method 'get'
    set load-balancing haproxy backend bk-01 http-check uri '/health'
    set load-balancing haproxy backend bk-01 http-check expect 'status 200'

    set load-balancing haproxy backend bk-01 server srv01 address '192.0.2.11'
    set load-balancing haproxy backend bk-01 server srv01 port '8881'
    set load-balancing haproxy backend bk-01 server srv01 check
    set load-balancing haproxy backend bk-01 server srv02 address '192.0.2.12'
    set load-balancing haproxy backend bk-01 server srv02 port '8882'
    set load-balancing haproxy backend bk-01 server srv02 check port '8892'

