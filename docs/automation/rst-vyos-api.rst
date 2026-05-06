:lastproofread: 2026-04-13

.. _vyosapi:

########
VyOS API
########

For instructions on configuring and enabling the API, see :ref:`http-api`.

**************
Authentication
**************

All endpoints, except one, accept HTTP POST requests. The API key must be 
provided as the ``key`` field in the form data. The only public endpoint 
accepts HTTP GET requests and supports optional query parameters.

Below are examples of API requests in cURL and Python. All other code examples 
in this documentation use cURL.

.. code-block:: none

   curl --location --request POST 'https://vyos/retrieve' \
   --form data='{"op": "showConfig", "path": []}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

.. code-block:: python

   import requests
   url = "https://vyos/retrieve"
   payload={'data': '{"op": "showConfig", "path": []}',
            'key': 'MY-HTTPS-API-PLAINTEXT-KEY'
           }
   headers = {}
   response = requests.request("POST", url, headers=headers, data=payload)
   print(response.text)


*************
API endpoints
*************
/info
=========

This is the only API endpoint that does not require authentication and can be 
accessed by anonymous users. The info endpoint returns general system 
information, including the VyOS version, system hostname, and a welcome banner.

This endpoint accepts **only** HTTP GET requests.

.. code-block:: none

    curl --location --request GET 'https://vyos/info'

    response
    {
        "success": true,
        "data": {
            "version": "1.5-rolling",
            "hostname": "vyos",
            "banner": "Welcome to VyOS"
        },
        "error": null
    }

**Query parameters**

This endpoint accepts two optional query parameters, version and hostname. Each 
parameter accepts values convertible to Boolean (e.g., ``yes/no``, ``1/0``, or 
``true/false``) to control the inclusion of related fields in the response.

If no query parameters are provided, both parameters default to ``true``.

.. code-block:: none

    curl --location --request GET 'https://vyos/info?version=1&hostname=1'

    response {
        "success": true,
        "data": {
            "version": "1.5-rolling",
            "hostname": "vyos",
            "banner": "Welcome to VyOS"
        },
        "error": null
    }

If either parameter is set to a value corresponding to false, its field is 
returned as an empty string in the response:

.. code-block:: none

    curl --location --request GET 'https://vyos/info?version=0&hostname=1'

    response {
        "success": true,
        "data": {
            "version": "",
            "hostname": "vyos",
            "banner": "Welcome to VyOS"
        },
        "error": null
    }

You do not need to specify both parameters if you want to hide only one. Any 
missing query parameter defaults to true.

.. code-block:: none

    curl --location --request GET 'https://vyos/info?hostname=no'

    response {
        "success": true,
        "data": {
            "version": "1.5-rolling",
            "hostname": "",
            "banner": "Welcome to VyOS"
        },
        "error": null
    }

Note that while you can disable output for both ``hostname`` and ``version``, 
the ``banner`` is always included in the response.

.. Important::
   
   The endpoint accepts **ONLY** ``hostname`` and ``version`` query
   parameters. Including any other parameters results in an HTTP 400 Bad Request.

.. code-block:: none

    curl --location --request GET \
        'https://192.168.56.119/info?hostname=1&url=https://evilsite.com'

    response {
        "success": false,
        "error": "{'type': 'extra_forbidden', 'loc': ('query', 'url'), 'msg': 'Extra inputs are not permitted', 'input': 'https://evilsite.com'}",
        "data": null
    }

Values passed to the query string are validated to ensure they are strictly 
Boolean. Other data types are not accepted.

.. code-block:: none

    curl --location --request GET 'https://vyos/info?hostname=1; eval"sudo rm -rf /"'

    response
    {
        "success": false,
        "error": "{'type': 'bool_parsing', 'loc': ('query', 'hostname'), 'msg': 'Input should be a valid boolean, unable to interpret input', 'input': '1; eval \"sudo rm -rf /\"'}",
        "data": null
    }

/retrieve
=========

The ``/retrieve`` endpoint returns either specific parts or the entire 
configuration.

To retrieve the entire configuration, pass an empty list to the ``path`` field.

.. code-block:: none

   curl --location --request POST 'https://vyos/retrieve' \
   --form data='{"op": "showConfig", "path": []}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'


   response (shortened)
   {
      "success": true,
      "data": {
         "interfaces": {
               "ethernet": {
                  "eth0": {
                     "address": "dhcp",
                     "duplex": "auto",
                     "hw-id": "50:00:00:01:00:00",
                     "speed": "auto"
                  },
                  "eth1": {
                     "duplex": "auto",
                     "hw-id": "50:00:00:01:00:01",
                     "speed": "auto"
      ...
      },
      "error": null
   }


To retrieve a specific configuration part, such as ``system syslog``, specify 
the desired path.

.. code-block:: none

   curl -k --location --request POST 'https://vyos/retrieve' \
   --form data='{"op": "showConfig", "path": ["system", "syslog"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'


   response:
   {
      "success": true,
      "data": {
         "global": {
               "facility": {
                  "all": {
                     "level": "info"
                  },
                  "protocols": {
                     "level": "debug"
                  }
               }
         }
      },
      "error": null
   }

If you only need the value of a multi-valued node, use the ``returnValues``
operation.

For example, to get the addresses of a ``dum0`` interface:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/retrieve' \
   --form data='{"op": "returnValues", "path": ["interfaces","dummy","dum0","address"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": [
         "10.10.10.10/24",
         "10.10.10.11/24",
         "10.10.10.12/24"
      ],
      "error": null
   }

To check whether a configuration path exists, use the ``exists`` operation. It 
returns ``true`` for an existing path:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/retrieve' \
   --form data='{"op": "exists", "path": ["service","https","api"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": true,
      "error": null
   }

It returns ``false`` for a non-existing path:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/retrieve' \
   --form data='{"op": "exists", "path": ["service","non","existent","path"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": false,
      "error": null
   }

/reset
======

The ``/reset`` endpoint runs the ``reset`` command.

.. code-block:: none

   curl --location --request POST 'https://vyos/reset' \
   --form data='{"op": "reset", "path": ["ip", "bgp", "192.0.2.11"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
     "success": true,
     "data": "",
     "error": null
   }

/reboot
=======

To initiate a reboot, use the ``/reboot`` endpoint.

.. code-block:: none

   curl --location --request POST 'https://vyos/reboot' \
   --form data='{"op": "reboot", "path": ["now"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
     "success": true,
     "data": "",
     "error": null
   }

/poweroff
=========

To power off the system, use the ``/poweroff`` endpoint.

.. code-block:: none

   curl --location --request POST 'https://vyos/poweroff' \
   --form data='{"op": "poweroff", "path": ["now"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
     "success": true,
     "data": "",
     "error": null
   }


/image
======

To add or delete an image, use the ``/image`` endpoint.

To add an image:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/image' \
   --form data='{"op": "add", "url": "https://downloads.vyos.io/rolling/current/amd64/vyos-rolling-latest.iso"}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response (shortened):
   {
      "success": true,
      "data": "Trying to fetch ISO file from https://downloads.vyos.io/rolling-latest.iso\n
               ...
               Setting up grub configuration...\nDone.\n",
      "error": null
   }

To delete an image, for example ``1.3-rolling-202006070117``:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/image' \
   --form data='{"op": "delete", "name": "1.3-rolling-202006070117"}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": "Deleting the \"1.3-rolling-202006070117\" image...\nDone\n",
      "error": null
   }


/show
=====

The ``/show`` endpoint runs operational mode commands and returns the resulting 
output.

For example, to show the installed images:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/show' \
   --form data='{"op": "show", "path": ["system", "image"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": "The system currently has the following image(s) installed:\n\n
                1: 1.4-rolling-202102280559 (default boot)\n
                2: 1.4-rolling-202102230218\n
                3: 1.3-beta-202102210443\n\n",
      "error": null
   }


/generate
=========

The ``/generate`` endpoint runs a ``generate`` command.

.. code-block:: none

   curl -k --location --request POST 'https://vyos/generate' \
   --form data='{"op": "generate", "path": ["pki", "wireguard", "key-pair"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": "Private key: CFZR2eyhoVZwk4n3JFPMJx3E145f1EYgDM+ubytXYVY=\n
               Public key: jjtpPT8ycI1Q0bNtrWuxAkO4k88Xwzg5VHV9xGZ58lU=\n\n",
      "error": null
   }


/configure
==========

The ``/configure`` endpoint accepts ``set``, ``delete``, and ``comment`` commands.

To apply a ``set`` command:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/configure' \
   --form data='{"op": "set", "path": ["interfaces", "dummy", "dum1", "address", "10.11.0.1/32"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": null,
      "error": null
   }


To apply a ``delete`` command:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/configure' \
   --form data='{"op": "delete", "path": ["interfaces", "dummy", "dum1", "address", "10.11.0.1/32"]}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": null,
      "error": null
   }

The API processes each request in a session and commits it. For components such 
as DHCP and PPPoE servers, IPsec, VXLAN, and other tunnels, VyOS requires the 
entire configuration block for a commit.  

The endpoint can process multiple commands if you pass them as a list to
the ``data`` field.

.. code-block:: none

   curl -k --location --request POST 'https://vyos/configure' \
   --form data='[{"op": "set","path":["interfaces","vxlan","vxlan1","remote","203.0.113.99"]}, {"op": "set","path":["interfaces","vxlan","vxlan1","vni","1"]}]' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": null,
      "error": null
   }


/config-file
============

The ``/config-file`` endpoint allows you to save, load, or merge a 
configuration. 

If you do not specify a file during the ``save`` operation, the configuration 
is automatically saved to ``/config/config.boot``.

.. code-block:: none

   curl -k --location --request POST 'https://vyos/config-file' \
   --form data='{"op": "save"}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": "Saving configuration to '/config/config.boot'...\nDone\n",
      "error": null
   }


To save a running configuration to a file:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/config-file' \
   --form data='{"op": "save", "file": "/config/test.config"}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": "Saving configuration to '/config/test.config'...\nDone\n",
      "error": null
   }


To load a configuration file:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/config-file' \
   --form data='{"op": "load", "file": "/config/test.config"}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": null,
      "error": null
   }

To merge a configuration file:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/config-file' \
   --form data='{"op": "merge", "file": "/config/test.config"}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": null,
      "error": null
   }

For both ``load`` and ``merge`` operations, you can pass a string in the 
request body. For example:

.. code-block:: none

   curl -k --location --request POST 'https://vyos/config-file' \
   --form data='{"op": "merge", "string": "interfaces {\nethernet eth1 {\naddress "192.168.2.137/24"\ndescription "test"\n}\n}\n"}' \
   --form key='MY-HTTPS-API-PLAINTEXT-KEY'

   response:
   {
      "success": true,
      "data": null,
      "error": null
   }

**************
Commit-confirm
**************

For the previous two endpoints, a ``commit`` command is executed automatically 
after a successful request operation (``set``, ``delete``, ``load``, ``merge``, 
or a list of ``set`` and ``delete`` operations). 

Alternatively, you can initiate a ``commit-confirm``. Include the 
``confirm_time`` field in your request and set it to an integer greater than 
``0``.

The following example uses the JSON format for brevity, though the standard 
form data format is equally valid:

.. code-block:: none

   curl -k -X POST -d '{"key": "MY-HTTPS-API-PLAINTEXT-KEY", "op": "merge", "string": "interfaces {\nethernet eth1 {\naddress '192.168.137.1/24'\ndescription 'internal'\n}\n}\n", "confirm_time": 1}' https://vyos/config-file

   response:
   {
      "success": true,
      "data": "Initialized commit-confirm; 1 minutes to confirm before reload\n",
      "error": null
   }

If not confirmed within the specified time, the committed changes will be 
reverted. To confirm and keep the changes:

.. code-block:: none

   curl -k -X POST -d '{"key": "MY-HTTPS-API-PLAINTEXT-KEY", "op": "confirm"}' https://vyos/config-file

   response:
   {
      "success": true,
      "data": "Reload timer stopped\n",
      "error": null
   }

If the commit is not confirmed, the revert behavior is controlled by:

.. code-block:: none

   vyos@vyos# set system config-management commit-confirm action
   Possible completions:
      reload               Reload previous configuration if not confirmed
      reboot               Reboot to saved configuration if not confirmed (default)
