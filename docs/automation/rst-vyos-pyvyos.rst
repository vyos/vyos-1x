:lastproofread: 2026-04-14

.. _vyos-pyvyos:

######
PyVyOS
######

PyVyOS is a Python library for configuring and managing VyOS devices through 
their API.

**Key resources:**

- `Documentation <https://pyvyos.readthedocs.io/en/latest/>`_: Provides 
  installation, configuration, and usage instructions.
- `GitHub repository <https://github.com/robertoberto/pyvyos>`_: Hosts the 
  source code.
- `PyPI <https://pypi.org/project/pyvyos/>`_: Hosts distribution packages for 
  installation via the Python package installer (``pip``).


Installation
------------

To install PyVyOS via ``pip``, run:

.. code-block:: bash

    pip install pyvyos

Getting started
---------------

Import and disable warnings for verify=false
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    import urllib3
    urllib3.disable_warnings()

Use API response class
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    @dataclass
    class ApiResponse:
        status: int
        request: dict
        result: dict
        error: str

Initialize a VyDevice object
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    from dotenv import load_dotenv
    load_dotenv()

    hostname = os.getenv('VYDEVICE_HOSTNAME')
    apikey = os.getenv('VYDEVICE_APIKEY')
    port = os.getenv('VYDEVICE_PORT')
    protocol = os.getenv('VYDEVICE_PROTOCOL')
    verify_ssl = os.getenv('VYDEVICE_VERIFY_SSL')

    verify = verify_ssl.lower() == "true" if verify_ssl else True 

    device = VyDevice(hostname=hostname, apikey=apikey, port=port, protocol=protocol, verify=verify)

Use PyVyOS
----------

Configure, then set
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    response = device.configure_set(path=["interfaces", "ethernet", "eth0", "address", "192.168.1.1/24"])
    if not response.error:
        print(response.result)

Configure, then show a single object value
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    response = device.retrieve_return_values(path=["interfaces", "dummy", "dum1", "address"])
    print(response.result)

Configure, then show object
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    response = device.retrieve_show_config(path=[])
    if not response.error:
        print(response.result)

Configure, then delete object
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    response = device.configure_delete(path=["interfaces", "dummy", "dum1"])

Configure, then save
^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    response = device.config_file_save()

Configure, then save file
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    response = device.config_file_save(file="/config/test300.config")

Show object
^^^^^^^^^^^

.. code-block:: none

    response = device.show(path=["system", "image"])
    print(response.result)

Generate object
^^^^^^^^^^^^^^^

.. code-block:: none

    randstring = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(20))
    keyrand =  f'/tmp/key_{randstring}'
    response = device.generate(path=["ssh", "client-key", keyrand])

Reset object
^^^^^^^^^^^^

.. code-block:: none

    response = device.reset(path=["conntrack-sync", "internal-cache"])
    if not response.error:
        print(response.result)

Configure, then load file
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    response = device.config_file_load(file="/config/test300.config")


.. _pyvyos: https://github.com/robertoberto/pyvyos
