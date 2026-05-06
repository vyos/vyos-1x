:lastproofread: 2024-07-03

#########
Container
#########

The VyOS container implementation is based on `Podman <https://podman.io/>`_ as
a deamonless container engine.

*************
Configuration
*************

.. cfgcmd:: set container name <name> image

    Sets the image name in the hub registry

    .. code-block:: none

      set container name mysql-server image mysql:8.0

    If a registry is not specified, Docker.io will be used as the container
    registry unless an alternative registry is specified using
    **set container registry <name>** or the registry is included
    in the image name

    .. code-block:: none

      set container name mysql-server image quay.io/mysql:8.0

.. cfgcmd:: set container name <name> entrypoint <entrypoint>

   Override the default entrypoint from the image for a container.

.. cfgcmd:: set container name <name> command <command>

    Override the default command from the image for a container.

.. cfgcmd:: set container name <name> arguments <arguments>

    Set the command arguments for a container.

.. cfgcmd:: set container name <name> host-name <hostname>

    Set the host name for a container.

.. cfgcmd:: set container name <name> allow-host-pid

    The container and the host share the same process namespace.
    This means that processes running on the host are visible inside the
    container, and processes inside the container are visible on the host.

    The command translates to "--pid host" when the container is created.

.. cfgcmd:: set container name <name> allow-host-networks

    Allow host networking in a container. The network stack of the container is
    not isolated from the host and will use the host IP.

    The command translates to "--net host" when the container is created.

    .. note:: **allow-host-networks** cannot be used with **network**

.. cfgcmd:: set container name <name> network <networkname>

    Attaches user-defined network to a container.
    Only one network must be specified and must already exist.

.. cfgcmd:: set container name <name> network <networkname> address <address>

    Optionally set a specific static IPv4 or IPv6 address for the container.
    This address must be within the named network prefix.

    .. note:: The first IP in the container network is reserved by the
       engine and cannot be used

.. cfgcmd:: set container name <name> name-server <address>

    Optionally set a custom name server.
    If a container network is used with DNS enabled,
    this setting will not have any effect.

.. cfgcmd:: set container name <name> description <text>

    Set a container description

.. cfgcmd:: set container name <name> environment <key> value <value>

    Add custom environment variables.
    Multiple environment variables are allowed.
    The following commands translate to "-e key=value" when the container
    is created.

    .. code-block:: none

        set container name mysql-server environment MYSQL_DATABASE value 'zabbix'
        set container name mysql-server environment MYSQL_USER value 'zabbix'
        set container name mysql-server environment MYSQL_PASSWORD value 'zabbix_pwd'
        set container name mysql-server environment MYSQL_ROOT_PASSWORD value 'root_pwd'

.. cfgcmd:: set container name <name> port <portname> source <portnumber>
.. cfgcmd:: set container name <name> port <portname> destination <portnumber>
.. cfgcmd:: set container name <name> port <portname> protocol <tcp | udp>

    Publish a port for the container.

    .. code-block:: none

        set container name zabbix-web-nginx-mysql port http source 80
        set container name zabbix-web-nginx-mysql port http destination 8080
        set container name zabbix-web-nginx-mysql port http protocol tcp

.. note:: Port publishing cannot be used with **network**. For this purpose, a workaround
          using destination NAT and static IP assignment for the container is available.

.. cfgcmd:: set container name <name> volume <volumename> source <path>
.. cfgcmd:: set container name <name> volume <volumename> destination <path>

    Mount a volume into the container

    .. code-block:: none

        set container name coredns volume 'corefile' source /config/coredns/Corefile
        set container name coredns volume 'corefile' destination /etc/Corefile

.. cfgcmd:: set container name <name> volume <volumename> mode <ro | rw>

    Volume is either mounted as rw (read-write - default) or ro (read-only)

.. cfgcmd:: set container name <name> tmpfs <tmpfsname> destination <path>

    Mount a tmpfs *(ramdisk)* filesystem to the given path within the container.

.. cfgcmd:: set container name <name> tmpfs <tmpfsname> size <MB>

    Size in MB for tmpfs filesystem, maximum size is 64GB or 50% of the
    systems total available memory.

.. cfgcmd:: set container name <name> uid <number>
.. cfgcmd:: set container name <name> gid <number>

    Set the User ID or Group ID of the container

.. cfgcmd:: set container name <name> restart [no | on-failure | always]

   Set the restart behavior of the container.

   - **no**: Do not restart containers on exit
   - **on-failure**: Restart containers when they exit with a non-zero
     exit code, retrying indefinitely (default)
   - **always**: Restart containers when they exit, regardless of status,
     retrying indefinitely

.. cfgcmd:: set container name <name> cpu-quota <num>

   This specifies the number of CPU resources the container can use.

   Default is 0 for unlimited.
   For example, 1.25 limits the container to use up to 1.25 cores
   worth of CPU time.
   This can be a decimal number with up to three decimal places.

   The command translates to "--cpus=<num>" when the container is created.

.. cfgcmd:: set container name <name> memory <MB>

   Constrain the memory available to the container.

   Default is 512 MB. Use 0 MB for unlimited memory.

.. cfgcmd:: set container name <name> device <devicename> source <path>
.. cfgcmd:: set container name <name> device <devicename> destination <path>

   Add a host device to the container.

.. cfgcmd:: set container name <name> capability <text>

   Set container capabilities or permissions.

   - **net-admin**: Network operations (interface, firewall, routing tables)
   - **net-bind-service**: Bind a socket to privileged ports
     (port numbers less than 1024)
   - **net-raw**: Permission to create raw network sockets
   - **setpcap**: Capability sets (from bounded or inherited set)
   - **sys-admin**: Administration operations (quotactl, mount, sethostname,
     setdomainame)
   - **sys-time**: Permission to set system clock

.. cfgcmd:: set container name <name> sysctl parameter <parameter> value <value>

   Set container sysctl values.

   The subset of possible parameters are:

   - Kernel Parameters: kernel.msgmax, kernel.msgmnb, kernel.msgmni, kernel.sem,
     kernel.shmall, kernel.shmmax, kernel.shmmni, kernel.shm_rmid_forced
   - Parameters beginning with fs.mqueue.*
   - Parameters beginning with net.* (only if user-defined network is used)

.. cfgcmd:: set container name <name> label <label> value <value>

   Add metadata label for this container.

.. cfgcmd:: set container name <name> disable

   Disable a container.

Container Health checks
=======================

By default, no health checks are run, even when defined by the image.

.. cfgcmd:: set container name <name> health-check

    Default health check is run for the container if defined by the image.

.. cfgcmd:: set container name <name> health-check command <command>

    Override the default health check command from the image for a container.

.. cfgcmd:: set container name <name> health check interval <interval>

    Override the default health-check interval. For example: `60`

.. cfgcmd:: set container name <name> health check timeout <timeout>

    Override the default health-check timeout. For example: `10`

.. cfgcmd:: set container name <name> health check retries <retries>

    Number of health check retries before container is considered unhealthy. For example: `1`

Container Networks
==================

.. cfgcmd:: set container network <name>

    Creates a named container network

.. cfgcmd:: set container network <name> description

    A brief description what this network is all about.

.. cfgcmd:: set container network <name> prefix <ipv4|ipv6>

    Define IPv4 and/or IPv6 prefix for a given network name.
    Both IPv4 and IPv6 can be used in parallel.

.. cfgcmd:: set container network <name> mtu <number>

    Configure :abbr:`MTU (Maximum Transmission Unit)` for a given network. It
    is the size (in bytes) of the largest ethernet frame sent on this link.

.. cfgcmd:: set container network <name> no-name-server

    Disable Domain Name System (DNS) plugin for this network.

.. cfgcmd:: set container network <name> vrf <nme>

    Bind container network to a given VRF instance.

Container Registry
==================

.. cfgcmd:: set container registry <name>

    Adds registry to list of unqualified-search-registries. By default, for any
    image that does not include the registry in the image name, VyOS will use
    docker.io and quay.io as the container registry.

.. cfgcmd:: set container registry <name> disable

    Disable a given container registry

.. cfgcmd:: set container registry <name> authentication username
.. cfgcmd:: set container registry <name> authentication password

    Some container registries require credentials to be used.

    Credentials can be defined here and will only be used when adding a
    container image to the system.

.. cfgcmd:: set container registry <name> insecure

    Allow registry access over unencrypted HTTP or TLS connections with
    untrusted certificates.

.. cfgcmd:: set container registry <name> mirror address <address>

.. cfgcmd:: set container registry <name> mirror host-name <host-name>

.. cfgcmd:: set container registry <name> mirror port <port>

.. cfgcmd:: set container registry <name> mirror path <path>

    Registry mirror, use ``(host-name|address)[:port][/path]``.

    If you have mirror http://192.168.1.1:8080 for docker.io, you can use ``docker.io/some/repo`` or run ``podman pull docker.io/some/repo``

    .. code-block:: none

        set container registry docker.io mirror address 192.168.1.1
        set container registry docker.io mirror port 8080
        set container registry docker.io insecure

    If http://192.168.1.1:8080 is your own registry, you can use ``192.168.1.1:8080/some/repo`` or run ``podman pull 192.168.1.1:8080/some/repo``

    .. code-block:: none

        set container registry 192.168.1.1:8080 insecure


Log Configuration
====================

.. cfgcmd:: set container name <name> log-driver [k8s-file | journald | none]

   Set the default log driver for containers.

   - **k8s-file**: Log to a plain text file in Kubernetes-style format.
   - **journald**: Log to the system journal
   - **none**: Disable logging for the container

   Current default is journald. 


******************
Operation Commands
******************

.. opcmd:: add container image <containername>

    Pull a new image for container

.. opcmd:: show container

    Show the list of all active containers.

.. opcmd:: show container image

    Show the local container images.

.. opcmd:: show container log <containername>

    Show logs from a given container

.. opcmd:: show container network

    Show a list available container networks

.. opcmd:: restart container <containername>

    Restart a given container

.. opcmd:: update container image <containername>

    Update container image

.. opcmd:: delete container image <image id|all> [force]

    Delete a particular container image based on it's image ID.
    You can also delete all container images at once.

    You can not delete a container image if it has more then one tag
    assigned, this is why there is a `force` option to pass down to
    the container image to also remove those images.

*********************
Example Configuration
*********************

    For the sake of demonstration, `example #1 in the official documentation
    <https://www.zabbix.com/documentation/current/manual/
    installation/containers>`_
    to the declarative VyOS CLI syntax.

    .. code-block:: none

        set container network zabbix prefix 172.20.0.0/16
        set container network zabbix description 'Network for Zabbix component containers'

        set container name mysql-server image mysql:8.0
        set container name mysql-server network zabbix

        set container name mysql-server environment 'MYSQL_DATABASE' value 'zabbix'
        set container name mysql-server environment 'MYSQL_USER' value 'zabbix'
        set container name mysql-server environment 'MYSQL_PASSWORD' value 'zabbix_pwd'
        set container name mysql-server environment 'MYSQL_ROOT_PASSWORD' value 'root_pwd'

        set container name zabbix-java-gateway image zabbix/zabbix-java-gateway:alpine-5.2-latest
        set container name zabbix-java-gateway network zabbix

        set container name zabbix-server-mysql image zabbix/zabbix-server-mysql:alpine-5.2-latest
        set container name zabbix-server-mysql network zabbix

        set container name zabbix-server-mysql environment 'DB_SERVER_HOST' value 'mysql-server'
        set container name zabbix-server-mysql environment 'MYSQL_DATABASE' value 'zabbix'
        set container name zabbix-server-mysql environment 'MYSQL_USER' value 'zabbix'
        set container name zabbix-server-mysql environment 'MYSQL_PASSWORD' value 'zabbix_pwd'
        set container name zabbix-server-mysql environment 'MYSQL_ROOT_PASSWORD' value 'root_pwd'
        set container name zabbix-server-mysql environment 'ZBX_JAVAGATEWAY' value 'zabbix-java-gateway'

        set container name zabbix-server-mysql port zabbix source 10051
        set container name zabbix-server-mysql port zabbix destination 10051

        set container name zabbix-web-nginx-mysql image zabbix/zabbix-web-nginx-mysql:alpine-5.2-latest
        set container name zabbix-web-nginx-mysql network zabbix

        set container name zabbix-web-nginx-mysql environment 'MYSQL_DATABASE' value 'zabbix'
        set container name zabbix-web-nginx-mysql environment 'ZBX_SERVER_HOST' value 'zabbix-server-mysql'
        set container name zabbix-web-nginx-mysql environment 'DB_SERVER_HOST' value 'mysql-server'
        set container name zabbix-web-nginx-mysql environment 'MYSQL_USER' value 'zabbix'
        set container name zabbix-web-nginx-mysql environment 'MYSQL_PASSWORD' value 'zabbix_pwd'
        set container name zabbix-web-nginx-mysql environment 'MYSQL_ROOT_PASSWORD' value 'root_pwd'

        set container name zabbix-web-nginx-mysql port http source 80
        set container name zabbix-web-nginx-mysql port http destination 8080
