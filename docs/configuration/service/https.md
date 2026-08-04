---
myst:
  html_meta:
    description: |
      VyOS provides an HTTP API for running operational-mode commands
      and managing configuration. The API is available as both REST and
      GraphQL, served by an HTTPS listener with configurable TLS.
    keywords: http-api, https, rest, graphql, api-key, jwt, tls, cors
---

(http-api)=

# HTTP API

VyOS provides an HTTP API. You can use it to run operational-mode
commands or to change or delete configuration. The API is available as
both a REST API and a GraphQL API.

For REST API request examples, endpoints, and authentication details,
see {ref}`vyosapi`.

```{note}
If no PKI certificate is configured for the service, VyOS automatically
generates a self-signed certificate. This is not recommended for production use.
```

## Configuration

### HTTPS listener

```{cfgcmd} set service https listen-address \<address\>

**Configure a local IPv4 or IPv6 address on which the HTTPS listener
accepts incoming connections.**

The IP address must already be assigned to a local interface. Repeat
the command to configure multiple IP addresses.

When unset, the listener accepts incoming connections on all local IP
addresses.
```

Example:

```none
set service https listen-address 192.0.2.1
set service https listen-address 2001:db8::1
```

```{cfgcmd} set service https port \<1-65535\>

**Configure the TCP port on which the HTTPS listener accepts incoming
connections.**

The default is 443.
```

```{note}
If the chosen port is already in use by another service, the commit
fails.
```

Example:

```none
set service https port 8443
```

```{cfgcmd} set service https vrf \<name\>

**Bind the HTTPS listener to the specified
{abbr}`VRF (Virtual Routing and Forwarding)` instance.**

The VRF must already be configured under `set vrf name <name>`.
```

Example:

```none
set service https vrf mgmt
```

```{cfgcmd} set service https allow-client address \<address\>

**Restrict access to the HTTPS API endpoints to the specified IPv4 or
IPv6 address or prefix.**

Repeat the command to allow multiple IP addresses or prefixes.

When unset, the API accepts connections from any IP address.
```

Example:

```none
set service https allow-client address 192.0.2.0/24
set service https allow-client address 2001:db8::/32
```

```{cfgcmd} set service https enable-http-redirect

**Enable redirection of incoming HTTP requests (port 80) to HTTPS.**

The redirect sends traffic to the default HTTPS port (443). If you
have changed the HTTPS port, the redirect will not work.
```

Example:

```none
set service https enable-http-redirect
```

```{cfgcmd} set service https request-body-size-limit \<1-256\>

**Configure the maximum size, in megabytes, of an HTTP request body
accepted by the listener.**

Requests exceeding this limit are rejected.

The default is 1.
```

Example:

```none
set service https request-body-size-limit 10
```

### TLS

```{cfgcmd} set service https tls-version \<1.2 | 1.3\>

**Enable a specific TLS protocol version for the HTTPS listener.**

Repeat the command to enable multiple protocol versions.

By default, both TLS 1.2 and TLS 1.3 are enabled.
```

Example:

```none
set service https tls-version 1.3
```

```{cfgcmd} set service https certificates certificate \<name\>

**Bind a TLS certificate from the PKI subsystem to the HTTPS
listener.**

The certificate must already be defined under
`set pki certificate <name>` with both a certificate and a private
key.
```

Example:

```none
set service https certificates certificate my-server-cert
```

```{cfgcmd} set service https certificates ca-certificate \<name\>

**Bind a {abbr}`CA (Certificate Authority)` certificate from the PKI
subsystem to the HTTPS listener.**

The CA must already be defined under `set pki ca <name>`. The CA
certificate is appended to the TLS certificate to form a full chain
presented to clients during the TLS handshake.
```

Example:

```none
set service https certificates ca-certificate my-internal-ca
```

```{cfgcmd} set service https certificates dh-params \<name\>

**Choose Diffie-Hellman parameters from the PKI subsystem for the HTTPS
listener.**

The parameters must already be defined under `set pki dh <name>` with
a key size of at least 2048 bits. The parameters are used by DHE
cipher suites in TLS 1.2. TLS 1.3 does not use them.
```

Example:

```none
set service https certificates dh-params my-dh-2048
```

### API authentication

```{cfgcmd} set service https api keys id \<name\> key \<apikey\>

**Configure an HTTP API key to authenticate REST requests, and GraphQL
requests unless GraphQL is switched to JWT token authentication.**

The key is specified in plaintext and grants full access to the API.

At least one key must be configured to use the REST API. GraphQL can
run without keys if JWT token authentication is enabled.
```

Example:

```none
set service https api keys id MY-HTTPS-API-ID key 'MY-HTTPS-API-PLAINTEXT-KEY'
```

### REST

```{cfgcmd} set service https api rest

**Enable the REST API for managing VyOS over HTTPS.**
```

Example:

```none
set service https api rest
```

```{cfgcmd} set service https api rest strict

**Reject delete requests on the `/configure` endpoint when the target
configuration path does not exist.**

Without this flag, such requests succeed silently.
```

Example:

```none
set service https api rest strict
```

```{cfgcmd} set service https api rest debug

**Log detailed error messages to the systemd journal when API
configuration requests fail.**

Without this flag, only short error messages are logged.
```

Example:

```none
set service https api rest debug
```

### GraphQL

```{cfgcmd} set service https api graphql introspection

**Enable GraphQL schema introspection.**

Authenticated clients can then query the endpoint for the full schema.
Disabled by default, and typically kept disabled in production due to
security concerns.
```

Example:

```none
set service https api graphql introspection
```

```{cfgcmd} set service https api graphql authentication type \<key | token\>

**Configure the authentication type for GraphQL requests:**

- `key`: Uses the API keys configured in `service https api keys`.
- `token`: Uses {abbr}`JWT (JSON Web Token)` tokens.

The default is `key`.
```

Example:

```none
set service https api graphql authentication type token
```

```{cfgcmd} set service https api graphql authentication expiration \<60-31536000\>

**Configure the lifetime, in seconds, of JWT tokens.**

The default is 3600.
```

Example:

```none
set service https api graphql authentication expiration 86400
```

```{cfgcmd} set service https api graphql authentication secret-length \<16-65535\>

**Configure the length, in bytes, of the shared secret used to sign
JWT tokens.**

The default is 32.
```

Example:

```none
set service https api graphql authentication secret-length 64
```

```{cfgcmd} set service https api graphql cors allow-origin \<origin\>

**Configure which websites (origins) can read responses from the
GraphQL API in a browser, using
{abbr}`CORS (Cross-Origin Resource Sharing)`.**

Repeat the command to allow multiple origins.
```

Example:

```none
set service https api graphql cors allow-origin https://app.example.com
```

## Example

The minimal configuration for a working REST API requires enabling REST
and configuring at least one API key:

```none
set service https api keys id MY-HTTPS-API-ID key MY-HTTPS-API-PLAINTEXT-KEY
set service https api rest
```
