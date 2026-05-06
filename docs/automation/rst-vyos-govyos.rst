:lastproofread: 2026-04-14

.. _vyos-govyos:

#######
Go-VyOS
#######

Go-VyOS is a Go library for configuring and managing VyOS devices through 
their API.

- `GitHub repository <https://github.com/ganawaj/go-vyos>`_: Hosts the source 
  code.
- `Documentation <https://pkg.go.dev/github.com/ganawaj/go-vyos@v0.1.0/vyos>`_: 
  Provides the complete API reference, including available types, functions, and 
  methods.


Installation
------------

To install Go-VyOS, run:

.. code-block:: bash

    go install "github.com/ganawaj/go-vyos/vyos"

Getting started
---------------

Import and disable TLS verification
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. stop_vyoslinter

.. code-block:: none

    import "github.com/ganawaj/go-vyos/vyos"
    client := vyos.NewClient(nil).WithToken("AUTH_KEY").WithURL("https://192.168.0.1").Insecure()

.. start_vyoslinter

Initialize a VyDevice object
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    import (
      "github.com/ganawaj/go-vyos/vyos"
      "os"
    )

    hostname := os.Getenv('VYDEVICE_HOSTNAME')
    port := os.Getenv('VYDEVICE_PORT')
    url := fmt.Sprintf("https://%s:%s", hostname, port)

    apikey := os.Getenv('VYDEVICE_APIKEY')
    verify_ssl := os.Getenv('VYDEVICE_VERIFY_SSL')

    client := vyos.NewClient(nil).WithToken(apikey).WithURL(url)

    if verify_ssl == "false" {
      client = client.Insecure()
    }

Use Go-VyOS
-----------

Configure, then set
^^^^^^^^^^^^^^^^^^^

.. stop_vyoslinter

.. code-block:: none

    out, resp, err := c.Conf.Set(ctx, "interfaces ethernet eth0 address 192.168.1.1/24")
    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)

.. start_vyoslinter

Show a single object value
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.Show.Do(ctx, "interfaces dummy dum1 address")
    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)
    fmt.Printf("Data: %v\n", out.Data)

Configure, then show object
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.Conf.Get(ctx, "interfaces dummy dum1", nil)
    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)
    fmt.Printf("Data: %v\n", out.Data)

Configure, then show multivalue object
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    options := RetrieveOptions{
        Multivalue: true,
    }

    out, resp, err := c.Conf.Get(ctx, "interfaces dummy dum1", options)
    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)


Configure, then delete object
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.Conf.Delete(ctx, "interfaces dummy dum1")
    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)

Configure, then save
^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.Conf.Save(ctx, "")

    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)

Configure, then save file
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.Conf.Save(ctx, "/config/test300.config")

    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)

Show object
^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.Show.Do(ctx, "system image")
    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)
    fmt.Printf("Data: %v\n", out.Data)

Generate object
^^^^^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.Generate.Do(ctx, "pki wireguard key-pair")
    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)
    fmt.Printf("Data: %v\n", out.Data)

Reset object
^^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.Reset.Do(ctx, "ip bgp 192.0.2.11")
    if err != nil {
        panic("Error: %v", err)
    }

    fmt.Println(out.Success)
    fmt.Printf("Data: %v\n", out.Data)

Configure, then load file
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

    out, resp, err := c.ConfigFile.Load(ctx, "/config/test300.config")

.. _go-vyos: https://github.com/ganawaj/go-vyos