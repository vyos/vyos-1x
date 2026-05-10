##########
Monitoring
##########

VyOS supports monitoring through Telegraf as well as through Prometheus exporters.

********
Telegraf
********

Telegraf is the open source server agent to help you collect metrics, events
and logs from your routers.

The following Telegraf plugins are configurable to export metrics and logs:
 * Azure Data Explorer
 * Prometheus Client
 * Splunk
 * InfluxDB
 * Loki


Azure data explorer
===================
Telegraf output plugin azure-data-explorer_.

.. cfgcmd:: set service monitoring telegraf azure-data-explorer authentication client-id <client-id>

   Authentication application client-id.

.. cfgcmd:: set service monitoring telegraf azure-data-explorer authentication client-secret <client-secret>

   Authentication application client-secret.

.. cfgcmd:: set service monitoring telegraf azure-data-explorer authentication tenant-id <tenant-id>

   Authentication application tenant-id

.. cfgcmd:: set service monitoring telegraf azure-data-explorer database <name>

   Remote database name.

.. cfgcmd:: set service monitoring telegraf azure-data-explorer group-metrics <single-table | table-per-metric>

   Type of metrics grouping when push to Azure Data Explorer. The default is
   ``table-per-metric``.

.. cfgcmd:: set service monitoring telegraf azure-data-explorer table <name>

   Name of the single table Only if set group-metrics single-table.

.. cfgcmd:: set service monitoring telegraf azure-data-explorer url <url>

   Remote URL.


Prometheus client
=================
Telegraf output plugin prometheus-client_
This plugin allows export of Telegraf metrics to Prometheus,
for Prometheus native metrics through exporters see section below.

.. cfgcmd:: set service monitoring telegraf prometheus-client

   Output plugin Prometheus client

.. cfgcmd:: set service monitoring telegraf prometheus-client allow-from <prefix>

   Networks allowed to query this server

.. cfgcmd:: set service monitoring telegraf prometheus-client authentication username <username>

   HTTP basic authentication username

.. cfgcmd:: set service monitoring telegraf prometheus-client authentication password <password>

   HTTP basic authentication username

.. cfgcmd:: set service monitoring telegraf prometheus-client listen-address <address>

   Local IP addresses to listen on

.. cfgcmd:: set service monitoring telegraf prometheus-client metric-version <1 | 2>

   Metris version, the default is ``2``

.. cfgcmd:: set service monitoring telegraf prometheus-client port <port>

   Port number used by connection, default is ``9273``

Example:

.. code-block:: none

  set service monitoring telegraf prometheus-client

.. code-block:: none

  vyos@r14:~$ curl --silent localhost:9273/metrics | egrep -v "#" |  grep cpu_usage_system
  cpu_usage_system{cpu="cpu-total",host="r14"} 0.20040080160320556
  cpu_usage_system{cpu="cpu0",host="r14"} 0.17182130584191915
  cpu_usage_system{cpu="cpu1",host="r14"} 0.22896393817971655


Splunk
======
Telegraf output plugin splunk_ HTTP Event Collector.

.. cfgcmd:: set service monitoring telegraf splunk authentication insecure

   Use TLS but skip host validation

.. cfgcmd:: set service monitoring telegraf splunk authentication token <token>

   Authorization token

.. cfgcmd:: set service monitoring telegraf splunk authentication url <url>

   Remote URL to Splunk collector

Example:

.. code-block:: none

  set service monitoring telegraf splunk authentication insecure
  set service monitoring telegraf splunk authentication token 'xxxxf5b8-xxxx-452a-xxxx-43828911xxxx'
  set service monitoring telegraf splunk url 'https://192.0.2.10:8088/services/collector'


InfluxDB
========
Telegraf output plugin influxdb_ to write metrics to ``InfluxDB`` via HTTP.

.. cfgcmd:: set service monitoring telegraf influxdb authentication organization <organization>

   Authentication organization name

.. cfgcmd:: set service monitoring telegraf influxdb authentication token <token>

   Authentication token

.. cfgcmd:: set service monitoring telegraf bucket <bucket>

   Remote ``InfluxDB`` bucket name

.. cfgcmd:: set service monitoring telegraf influxdb port <port>

   Remote port

.. cfgcmd:: set service monitoring telegraf influxdb url <url>

   Remote URL


Example:

.. code-block:: none

  set service monitoring telegraf influxdb authentication organization 'vyos'
  set service monitoring telegraf influxdb authentication token 'ZAml9Uy5wrhA...=='
  set service monitoring telegraf influxdb bucket 'bucket_vyos'
  set service monitoring telegraf influxdb port '8086'
  set service monitoring telegraf influxdb url 'http://r1.influxdb2.local'


Loki
====

Telegraf can be used to send logs to loki_ using tags as labels.

.. cfgcmd:: set service monitoring telegraf loki port <port>

   Remote Loki port

   Default is 3100

.. cfgcmd:: set service monitoring telegraf loki url <url>

   Remote Loki url

.. cfgcmd:: set service monitoring telegraf loki authentication username <username>
.. cfgcmd:: set service monitoring telegraf loki authentication password <password>

   HTTP basic authentication.

   If either is set both must be set.

.. cfgcmd:: set service monitoring telegraf loki metric-name-label <label>

   Label to use for the metric name when sending metrics.

   If set to an empty string, the label will not be added.
   This is NOT recommended, as it makes it impossible to differentiate
   between multiple metrics.

.. _azure-data-explorer: https://github.com/influxdata/telegraf/tree/master/plugins/outputs/azure_data_explorer
.. _prometheus-client: https://github.com/influxdata/telegraf/tree/master/plugins/outputs/prometheus_client
.. _influxdb: https://github.com/influxdata/telegraf/tree/master/plugins/outputs/influxdb_v2
.. _splunk: https://www.splunk.com/en_us/blog/it/splunk-metrics-via-telegraf.html
.. _loki: https://github.com/influxdata/telegraf/tree/master/plugins/outputs/loki


**********
Prometheus
**********

The following Prometheus exporters are configurable to export metrics:
 * Node Exporter
 * FRR Exporter


Node Exporter
=============
Prometheus node_exporter_ which provides a wide range of hardware and OS metrics.

.. cfgcmd:: set service monitoring prometheus node-exporter listen-address <address>

  Configure the address node_exporter is listening on.

.. cfgcmd:: set service monitoring prometheus node-exporter port <port>

  Configure the port number node_exporter is listening on.

.. cfgcmd:: set service monitoring prometheus node-exporter vrf <name>

  Configure name of the :abbr:`VRF (Virtual Routing and Forwarding)` instance.

.. cfgcmd:: set service monitoring prometheus node-exporter collectors textfile

  Configure textfile collector to export custom metrics read from
  `/run/node_exporter/collector`


FRR Exporter
============
Prometheus frr_exporter_ which provides free range routing metrics.

.. cfgcmd:: set service monitoring prometheus frr-exporter listen-address <address>

  Configure the address frr_exporter is listening on.

.. cfgcmd:: set service monitoring prometheus frr-exporter port <port>

  Configure the port number frr_exporter is listening on.

.. cfgcmd:: set service monitoring prometheus frr-exporter vrf <name>

  Configure name of the :abbr:`VRF (Virtual Routing and Forwarding)` instance.


Blackbox Exporter
=================
Prometheus blackbox_exporter_ which allows probing of endpoints over
HTTP, HTTPS, DNS, TCP, ICMP and gRPC .

.. cfgcmd:: set service monitoring prometheus blackbox-exporter listen-address <address>

  Configure the address blackbox_exporter is listening on.

.. cfgcmd:: set service monitoring prometheus blackbox-exporter port <port>

  Configure the port number blackbox_exporter is listening on.

.. cfgcmd:: set service monitoring prometheus blackbox-exporter vrf <name>

  Configure name of the :abbr:`VRF (Virtual Routing and Forwarding)` instance.

Configuring modules
-------------------
Blackbox exporter can be configured with different modules for probing DNS or ICMP.

DNS module example:

.. code-block:: none

  set service monitoring prometheus blackbox-exporter modules dns name dns4 preferred-ip-protocol ipv4
  set service monitoring prometheus blackbox-exporter modules dns name dns4 query-name vyos.io
  set service monitoring prometheus blackbox-exporter modules dns name dns4 query-type A

ICMP module example:

.. code-block:: none

  set service monitoring prometheus blackbox-exporter modules icmp name ping6 preferred-ip-protocol ipv6
  set service monitoring prometheus blackbox-exporter modules icmp name ping6 ip-protocol-fallback
  set service monitoring prometheus blackbox-exporter modules icmp name ping6 timeout 3

.. _node_exporter: https://github.com/prometheus/node_exporter
.. _frr_exporter: https://github.com/tynany/frr_exporter
.. _blackbox_exporter: https://github.com/prometheus/blackbox_exporter
