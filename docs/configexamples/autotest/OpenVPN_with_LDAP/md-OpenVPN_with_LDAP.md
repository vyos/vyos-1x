(examples-openvpn-with-ldap)=

# OpenVPN with LDAP

```{eval-rst}
| Testdate: 2023-05-11
| Version: 1.4-rolling-202305100734
```

This LAB shows how to use OpenVPN with a Active Directory authentication method.

Topology consists of:
: - Windows Server 2019 with a running Active Directory
  - VyOS as a OpenVPN Server
  - VyOS as Client

```{image} _include/topology.webp
:alt: OpenVPN with LDAP topology image
```


## Active Directory on Windows server

The lab assumes a full running Active Directory on the Windows Server.
Here are some PowerShell commands to quickly add a Test Active Directory.

```powershell
# install the Active Directory Server role
Install-WindowsFeature AD-Domain-Services -IncludeManagementTools

# install the Active Directory Server role
Install-ADDSForest -DomainName "vyos.local" -DomainNetBiosName "VYOS" -InstallDns:$true -NoRebootCompletion:$true

# create test user01 and binduser
New-ADUser binduser -AccountPassword(Read-Host -AsSecureString "Input Password") -Enabled $true
New-ADUser user01 -AccountPassword(Read-Host -AsSecureString "Input Password") -Enabled $true
```


## Configure VyOS as OpenVPN Server

In this example OpenVPN will be setup with a client certificate and username / password authentication.

First a CA, a signed server and client ceftificate and a Diffie-Hellman parameter musst be generated and installed.
Please look {ref}`here <configuration/pki/index:pki>` for more information.

```{eval-rst}
| Add the LDAP plugin configuration file `/config/auth/ldap-auth.config`
```

```{eval-rst}
| Check all possible settings `here <https://github.com/threerings/openvpn-auth-ldap/blob/master/auth-ldap.conf>`_.
```

```{literalinclude} _include/ldap-auth.config
:language: none
```

Now generate all required certificates on the ovpn-server:

First the CA

```none
vyos@ovpn-server# run generate pki ca install OVPN-CA
```

after this create a signed server and a client certificate

```none
vyos@ovpn-server# run generate pki certificate sign OVPN-CA install SRV
vyos@ovpn-server# run generate pki certificate sign OVPN-CA install CLIENT
```

and last the DH Key

```none
vyos@ovpn-server# run generate pki dh install DH
```

after all these steps the config look like this:

```none
set pki ca OVPN-CA certificate 'MIIFnTCCA4WgAwIBAgIUIPFIXvCxYdavCnSPFNjr6lUtlsswDQYJKoZIhvcNAQELBQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0yMzA1MTExMjM4MjJaFw0zMzA1MDgxMjM4MjJaMFcxCzAJBgNVBAYTAkdCMRMwEQYDVQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5T1MxEDAOBgNVBAMMB3Z5b3MuaW8wggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQDg45vAzS6xNqU+Pa7wk1Imt1/az1C22Sbp3wPJLfgOmy0K3TA5qVsx/c/8gatsatMkCsekGnK5BPzCDd5eCCLo//B25HFO6fBYRNvHvVyCUx7QEXw4FHFNG88zCIizx114AGtVwZfGGG9xCc53xjLPUpH6iqTXme41cCFFQlqXwZ7fuySieSdoV8SAsJTTOsGCEUEcDEnNPn6tX3KWTzNuyFPECy8WCmNgWNyG2nmH+U7WRTX0ehZ5dZyU5au7TxpRN4a+JtE0gNqcWJ+nh1A543q2pcRoQpPAzHFclgj8wG/EyauQMY/LC4tLc6moPaNlTwA9HJv8s6xUqpzNptDoUHKOqKuw2JRFnno5SCQ788KkKNgVWBy2o3BGoewfHFhAdR61CXeLpmuneuhi96GcM031gW8ptXbd4DkCF7H6KRtqeIvwiyG79ttC8kZf01Sn1fM5fTjGxaE38dAk/RchtHRC6rtFavHJjB2cUcCkhhQofUE6IR2dYJZ1cw0Wy5CI3bXHf43BpvDGmuxIlNGirTq8wf5RCWzDJJgmkQpYhUYe8x4faF4gTo00uH4ZvAYjQu3JNZGkb50p4kM9Mu5rQAiZJUeMAz/QD+EIV9xXgOk14+BbnHKWbZ7Ou5emewFuE/bjl79oNJklpXdc4soRkCPCTEGK3zDBdmUtCYk1DwIDAQABo2EwXzAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAdBgNVHSUEFjAUBggrBgEFBQcDAgYIKwYBBQUHAwEwHQYDVR0OBBYEFP5NDac/yC+mQmaTpZDUv9GZMGMBMA0GCSqGSIb3DQEBCwUAA4ICAQDEqpF2ibwYFxsF1XDIPS5/Gs0sZTZBuByNm5d2+jTyO7d5alZUdbvobbwhxZOhWasmFNyPLr4TYmZm5zF+efFsiOxjyRuEoVU+Fe8rZmpRIF/+6+nYX5r9vMI4QxGjeeyP20OHJ85Kvz182CTsITrM15Vw/kVVjAVzFI5Gm/QolalAoFQza9rAL4kDqaUszjHjPbysvDpGF+NLPjiYDHXcty/BC48bnuzAeEM60SGZ7EXvf8l0X8YsO7z39w6780A/3rbZvFhCYMKp/+p5xBRDjnX91dM6DJw73RwYQ1KHbHk9wWUwnL1giL71jzp/y4Oj6SSK2PQv+OnO80J6Zg06WIQx9xYcxr108Xh9FotUrlG7GYPI3Udf95t6SjuydDhULAVD0lMBxlDe9DHW1k1q1pOXaHZg926tY66xx/lda6dcuwJjA2Dx5JI6L0u9ureQmQAtxvnoTCtf+hR1iX/IkskZCKs34SjNiCnBuw/DNfdOpfaABm7y+tWiXBwnu5l/K8poXcQYQByyZj6YMmpgsbVPr5KNsLWOgRA81M6IPof8qxvnFrkazhiQWh1YHSjnaHtA3z5/BdgwHVICuFyrIOlbkKyJOjKcKBsDdMwIV0tsnpnyli2xEPZKu1tAQFAavXrK/RGYYhOZ3e0aRSV8hlP8i/mf7p0I45cJiBCqPg=='
set pki ca OVPN-CA private key '<REDACTED>'
set pki certificate SRV certificate 'MIIFtTCCA52gAwIBAgIUeZnSAMPohIvKL/1Fy/pW2cV73HkwDQYJKoZIhvcNAQELBQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0yMzA1MTExMjM4MzFaFw0zMzA1MDgxMjM4MzFaMFsxCzAJBgNVBAYTAkdCMRMwEQYDVQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5T1MxFDASBgNVBAMMC292cG4tc2VydmVyMIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEApDWzTcB5LFM/tacaRHvpchBKLigJ5FlqNNfJ2vnP87KfCmTA5tkWF7MtuY990tHZtl1vQ3Pim4d6XBOngiQmaw7tZeWAIrv1L2/VBjORUrLrQhkkg9nSpcYFxoyUQzukTY75PcwhYLkS6ZO/vPPSBuh97f3XR645Aauf7ZIk2NsUidP2uGZz/Sr5VC7ovH2l3zz1kIHPCinfvpPEVb5oTt7qEffk4vnKjy9RY+H1hZowvcAp1zfLaOt/dXaK6vfNutbmwDHbYAlIals0EcjtTr+63ymxmupn7RBjgWtK7MgocGZnt6HKJ4J6teP3WgiSd+I9pdFG4wHZOSVL3axf3rBx7q09DMn/Snvfbly+SlhXw9Ebk368J6j6rhNUkxo/M9fbfgxS0JnNjHInRNAvRQW5CgQfT9KyUdxR63BeSnngk2XYX+bDinb0ig+VDpZcr6PgOBR8aNFsCPbXRwDy0bmuFnFYMzs/7ZmFQhzE6rQykHvVvAsyv7FYrlW0E02H4+Xe6bEVpE1fLcH8OCGY2cfuTfq1Ax6R4r+tdHYW1kzFLjwdh3uqTLF11zcbkAwd78E/ItrfEadvgxrYR9gfhX79AkK0VHmZ/hzrLFeGznnVcqoTKgq21dfMfQG2P13QvqS7tCE5swM9N09ASVrifyVDuoL6jaW96wgeqR6eHMECAwEAAaN1MHMwDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCB4AwEwYDVR0lBAwwCgYIKwYBBQUHAwEwHQYDVR0OBBYEFE1U3Zamfuv6ocYiF9q7H//U8h+AMB8GA1UdIwQYMBaAFP5NDac/yC+mQmaTpZDUv9GZMGMBMA0GCSqGSIb3DQEBCwUAA4ICAQBZwHvGj/jziNFwXS2W1Q11I12YANmVhISP39AA7DNhXR+E1hXFs+U52ehurZoLTi5YTjd8PD0KcE58mw8CLsFQB/+pni9EwJuAhpMb6XsmYEp0PeOH7C/q5eOc4TB/NBsvEa5IdTmUoewmjubKeJ8OHdRBMI77Me53lSC6iskc9DGyixSLqQogQW4aiTposFJOW/YugBy7kiuygmFNJv4luDbyRBb9131zH0qSSishLT4Bp5lXQNYWI4AU0JeyQcYaSHWCr0h6H9GN3QOf/emc3/2Tee40FcEMsszJBRnQ3IISzU5xVLlfU02SJMpjvFT2MGfHAs7obrNbwiFeoLZ6fQeGLe53aOQ5M9XeW5bdIeR2ZrLoO1hW33x5jYI8nLnU0FnqpMMY14r7LZE/mjwfdrTsGChFzsLasB0Tj++mGMOXw3DSusppub17AE2bO2uO6J9XMlbkOC8EmDCF1Hetija4D3aunhtu6jRBOcR8DHVBqNae2YgUk1ALqGrNUGFH4bEioTjDDx2GieOtp9rUwJMlkAyUEe0k/wzcBLjZaO8KBCtrmTdr1wMXizPT+XcjAlzRNXvHiZFq0NG5Rnim+LH9tp90EHzO7EeVXV+LegnIKQqboIrY3KOw5Qx8ska+t1WrWHpyzpwsA0WjA6sDTyWthgNYSxb1ikNGO8STCA=='
set pki certificate SRV private key '<REDACTED>'
set pki certificate CLIENT certificate 'MIIFsDCCA5igAwIBAgIUSzQgwzGsfJFecGxCwLXVsGCLMkAwDQYJKoZIhvcNAQELBQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0yMzA1MTExMjM4MzlaFw0zMzA1MDgxMjM4MzlaMFYxCzAJBgNVBAYTAkdCMRMwEQYDVQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5T1MxDzANBgNVBAMMBmNsaWVudDCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBANHNJOSwcDbRqziL1gXYnHIq7P7vEUFvS8d/XLYJ1xIpcYTRXTut2CTGRar7fZZicu7x0yoK4TzrHvGVf1o4NC4NSGV5RX6kwRdrfWBmvpIkjSLGtCREFyhb+PHDpnsIS7cfN9udC0vocqVlx/xM/sfcP6Vja/uFp+9TQcneJIxYw34zkF+TtOVbE3pP5VxU7ZAj8F5/q1ONhTMdzG4Ol4/0nBqZfdYA3LVDeSSNIJNF5jlaKXXFHz1EJRemTYDx+f5bfCVcK2Qs8fU9jCFBlATjMu9O5rgk6nMLRwEnJZuZ1gj2tWQvz4e9yo5yUqf1PUhOrn3c81MRliUNHKr+CkxgQJal6P3Ar3q4iftJih3K+/j4o194mQ/Dt/Et+/Qn/DUFk2FB0rTMcQwJLTEAzxtTdmBJeJpipIPDR0u7UMZLNh/raQ8s3FsbY4uYORt2f5YQlCVHbth4dRa9xa+oRbm7eomNACIbWfkLh5Bzud1+qIfdBMZKaZbnf0HEeuH0J5LBJeova8EPxWbYMJPrRHzu5gowkIKl+uIxcy8IiNTA9YEoJVonCjmlr8NEtYShrIVbicdMNSI3pOQR60MFhkHwBjSU2l/z+4wwLxtzq/c2xKw9yrOZ46ZVLwGDFq8rPwp7/P9r6mDKsbn6jIvGOeH71dMZvoc4lCaClw+hKIzLAgMBAAGjdTBzMAwGA1UdEwEB/wQCMAAwDgYDVR0PAQH/BAQDAgeAMBMGA1UdJQQMMAoGCCsGAQUFBwMCMB0GA1UdDgQWBBS6j30FmL6kZW7rDH8QjRMoWoA/njAfBgNVHSMEGDAWgBT+TQ2nP8gvpkJmk6WQ1L/RmTBjATANBgkqhkiG9w0BAQsFAAOCAgEANW2Y4bgaB9oexEjj6rkGvePtQmXRkF/adVQREY9iZDGTe72ePybVzrfMkZHjse3o7JvXWRIVVztWSzEpv5noIOX7lAioGG3wsFTHotTFR0zrYJHXHBcV2Neq4Kx2Ta/TZwD8QnZHAAxEQ1pYb4fxwN/A60VElAZoz9zYsbrJyVrfuHDL9queQxPFzqis+7W1BiVIcv4rn0DMQ560jTGh4t4rImOSu5gUsUrQaih85XDdOBPxViSNwfVdZJIgbvamudpfEaKsIun/uCjcxpNnzIp0rhyYmDeqVat4GnTV7Sy48e/Uvcq71ZWbBYJF4+yW4pylIU2Sh/Uy2sAz4C2M71FlFB7qsmcnPRsFFHf+r1NyD1lkVI9k2371fTG/Kub9V0rOz4pvKz4Em5b4MUPdDbZOqJ8hQ+atGE3ovFJIovA3NFb0OtnyC4l+kG7dfjqFudOnmDa+Qsya+2YOxBZBIRfuhlXhb6Y6Smsk9R6x0jBmcQTPS5ZmvKaTxQCFc53xMdQNAswjiI2L9rw4BcqQfVmf/vpoN+VusD/XEv2V0Ixm10YybA7BI/tixh9vwj3fdQXVLy3jSYjVBd5WOFPizbQZeD10ElvlLqZZyWrP/Wre7Nmi/gEOnhBXXmo034fFF/vXf0JRpQsd2oDs24+4XwZYb8mbM31j7Nx8YvhR+64='
set pki certificate CLIENT private key '<REDACTED>'
set pki dh DH parameters 'MIIBCAKCAQEAzPOQWrWaIX2qt4sbV6bRbUnFx4jmeE+WXC8GIvulnC4pIr1nt2Gc/7uNfEPjDZ4X6csD3X6zAWxtSuWeNuml9Yuy+tS8gI7d0FlbQRAFO/9GIlRuVdMcbCtEhg8ja7Y0g3fQjOSQJ9mqFo7sRoXyYQALD+MDEJOxhnV7neCrgDi1pqnN4xZLoR9DLARp0ad30VIvnv0ay55wxFWAKh2iwNRwyeXIEOtUDBkfcLGSNNfK0kQsos/J8Q+7YXmk4cN9tiVX4xR92edVO4z/vhMkjsGKLSDm/E6EMusX+N0UhQ3dv7qDgeSS8vDsqBm8XJonumNZLvFbYt2ARGRZYL6DUwIBAg=='
```

Once all the required certificates and keys are installed, the remaining
OpenVPN Server configuration can be carried out.

```{literalinclude} _include/ovpn-server.conf
:language: none
```


## Client configuration

One advantage of having the client certificate stored is the ability to create the client configuration.

```none
vyos@ovpn-server:~$ generate openvpn client-config interface vtun10 ca OVPN-CA certificate CLIENT
```

save the output to a file and import it in nearly all openvpn clients.

```none
client
nobind
remote 198.51.100.254 1194
remote-cert-tls server
proto udp
dev tun
dev-type tun
persist-key
persist-tun
verb 3

# Encryption options

keysize 256
comp-lzo no

<ca>
-----BEGIN CERTIFICATE-----
MIIFnTCCA4WgAwIBAgIUIPFIXvCxYdavCnSPFNjr6lUtlsswDQYJKoZIhvcNAQEL
BQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcM
CVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0y
MzA1MTExMjM4MjJaFw0zMzA1MDgxMjM4MjJaMFcxCzAJBgNVBAYTAkdCMRMwEQYD
VQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5
T1MxEDAOBgNVBAMMB3Z5b3MuaW8wggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIK
AoICAQDg45vAzS6xNqU+Pa7wk1Imt1/az1C22Sbp3wPJLfgOmy0K3TA5qVsx/c/8
gatsatMkCsekGnK5BPzCDd5eCCLo//B25HFO6fBYRNvHvVyCUx7QEXw4FHFNG88z
CIizx114AGtVwZfGGG9xCc53xjLPUpH6iqTXme41cCFFQlqXwZ7fuySieSdoV8SA
sJTTOsGCEUEcDEnNPn6tX3KWTzNuyFPECy8WCmNgWNyG2nmH+U7WRTX0ehZ5dZyU
5au7TxpRN4a+JtE0gNqcWJ+nh1A543q2pcRoQpPAzHFclgj8wG/EyauQMY/LC4tL
c6moPaNlTwA9HJv8s6xUqpzNptDoUHKOqKuw2JRFnno5SCQ788KkKNgVWBy2o3BG
oewfHFhAdR61CXeLpmuneuhi96GcM031gW8ptXbd4DkCF7H6KRtqeIvwiyG79ttC
8kZf01Sn1fM5fTjGxaE38dAk/RchtHRC6rtFavHJjB2cUcCkhhQofUE6IR2dYJZ1
cw0Wy5CI3bXHf43BpvDGmuxIlNGirTq8wf5RCWzDJJgmkQpYhUYe8x4faF4gTo00
uH4ZvAYjQu3JNZGkb50p4kM9Mu5rQAiZJUeMAz/QD+EIV9xXgOk14+BbnHKWbZ7O
u5emewFuE/bjl79oNJklpXdc4soRkCPCTEGK3zDBdmUtCYk1DwIDAQABo2EwXzAP
BgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAdBgNVHSUEFjAUBggrBgEF
BQcDAgYIKwYBBQUHAwEwHQYDVR0OBBYEFP5NDac/yC+mQmaTpZDUv9GZMGMBMA0G
CSqGSIb3DQEBCwUAA4ICAQDEqpF2ibwYFxsF1XDIPS5/Gs0sZTZBuByNm5d2+jTy
O7d5alZUdbvobbwhxZOhWasmFNyPLr4TYmZm5zF+efFsiOxjyRuEoVU+Fe8rZmpR
IF/+6+nYX5r9vMI4QxGjeeyP20OHJ85Kvz182CTsITrM15Vw/kVVjAVzFI5Gm/Qo
lalAoFQza9rAL4kDqaUszjHjPbysvDpGF+NLPjiYDHXcty/BC48bnuzAeEM60SGZ
7EXvf8l0X8YsO7z39w6780A/3rbZvFhCYMKp/+p5xBRDjnX91dM6DJw73RwYQ1KH
bHk9wWUwnL1giL71jzp/y4Oj6SSK2PQv+OnO80J6Zg06WIQx9xYcxr108Xh9FotU
rlG7GYPI3Udf95t6SjuydDhULAVD0lMBxlDe9DHW1k1q1pOXaHZg926tY66xx/ld
a6dcuwJjA2Dx5JI6L0u9ureQmQAtxvnoTCtf+hR1iX/IkskZCKs34SjNiCnBuw/D
NfdOpfaABm7y+tWiXBwnu5l/K8poXcQYQByyZj6YMmpgsbVPr5KNsLWOgRA81M6I
Pof8qxvnFrkazhiQWh1YHSjnaHtA3z5/BdgwHVICuFyrIOlbkKyJOjKcKBsDdMwI
V0tsnpnyli2xEPZKu1tAQFAavXrK/RGYYhOZ3e0aRSV8hlP8i/mf7p0I45cJiBCq
Pg==
-----END CERTIFICATE-----

</ca>

<cert>
-----BEGIN CERTIFICATE-----
MIIFsDCCA5igAwIBAgIUSzQgwzGsfJFecGxCwLXVsGCLMkAwDQYJKoZIhvcNAQEL
BQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcM
CVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0y
MzA1MTExMjM4MzlaFw0zMzA1MDgxMjM4MzlaMFYxCzAJBgNVBAYTAkdCMRMwEQYD
VQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5
T1MxDzANBgNVBAMMBmNsaWVudDCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoC
ggIBANHNJOSwcDbRqziL1gXYnHIq7P7vEUFvS8d/XLYJ1xIpcYTRXTut2CTGRar7
fZZicu7x0yoK4TzrHvGVf1o4NC4NSGV5RX6kwRdrfWBmvpIkjSLGtCREFyhb+PHD
pnsIS7cfN9udC0vocqVlx/xM/sfcP6Vja/uFp+9TQcneJIxYw34zkF+TtOVbE3pP
5VxU7ZAj8F5/q1ONhTMdzG4Ol4/0nBqZfdYA3LVDeSSNIJNF5jlaKXXFHz1EJRem
TYDx+f5bfCVcK2Qs8fU9jCFBlATjMu9O5rgk6nMLRwEnJZuZ1gj2tWQvz4e9yo5y
Uqf1PUhOrn3c81MRliUNHKr+CkxgQJal6P3Ar3q4iftJih3K+/j4o194mQ/Dt/Et
+/Qn/DUFk2FB0rTMcQwJLTEAzxtTdmBJeJpipIPDR0u7UMZLNh/raQ8s3FsbY4uY
ORt2f5YQlCVHbth4dRa9xa+oRbm7eomNACIbWfkLh5Bzud1+qIfdBMZKaZbnf0HE
euH0J5LBJeova8EPxWbYMJPrRHzu5gowkIKl+uIxcy8IiNTA9YEoJVonCjmlr8NE
tYShrIVbicdMNSI3pOQR60MFhkHwBjSU2l/z+4wwLxtzq/c2xKw9yrOZ46ZVLwGD
Fq8rPwp7/P9r6mDKsbn6jIvGOeH71dMZvoc4lCaClw+hKIzLAgMBAAGjdTBzMAwG
A1UdEwEB/wQCMAAwDgYDVR0PAQH/BAQDAgeAMBMGA1UdJQQMMAoGCCsGAQUFBwMC
MB0GA1UdDgQWBBS6j30FmL6kZW7rDH8QjRMoWoA/njAfBgNVHSMEGDAWgBT+TQ2n
P8gvpkJmk6WQ1L/RmTBjATANBgkqhkiG9w0BAQsFAAOCAgEANW2Y4bgaB9oexEjj
6rkGvePtQmXRkF/adVQREY9iZDGTe72ePybVzrfMkZHjse3o7JvXWRIVVztWSzEp
v5noIOX7lAioGG3wsFTHotTFR0zrYJHXHBcV2Neq4Kx2Ta/TZwD8QnZHAAxEQ1pY
b4fxwN/A60VElAZoz9zYsbrJyVrfuHDL9queQxPFzqis+7W1BiVIcv4rn0DMQ560
jTGh4t4rImOSu5gUsUrQaih85XDdOBPxViSNwfVdZJIgbvamudpfEaKsIun/uCjc
xpNnzIp0rhyYmDeqVat4GnTV7Sy48e/Uvcq71ZWbBYJF4+yW4pylIU2Sh/Uy2sAz
4C2M71FlFB7qsmcnPRsFFHf+r1NyD1lkVI9k2371fTG/Kub9V0rOz4pvKz4Em5b4
MUPdDbZOqJ8hQ+atGE3ovFJIovA3NFb0OtnyC4l+kG7dfjqFudOnmDa+Qsya+2YO
xBZBIRfuhlXhb6Y6Smsk9R6x0jBmcQTPS5ZmvKaTxQCFc53xMdQNAswjiI2L9rw4
BcqQfVmf/vpoN+VusD/XEv2V0Ixm10YybA7BI/tixh9vwj3fdQXVLy3jSYjVBd5W
OFPizbQZeD10ElvlLqZZyWrP/Wre7Nmi/gEOnhBXXmo034fFF/vXf0JRpQsd2oDs
24+4XwZYb8mbM31j7Nx8YvhR+64=
-----END CERTIFICATE-----

</cert>

<key>
-----BEGIN PRIVATE KEY-----
...REDACTED...
-----END PRIVATE KEY-----

</key>
```


### Configure VyOS as client

```none
set interfaces openvpn vtun10 authentication username 'user01'
set interfaces openvpn vtun10 authentication password '$ecret'
set interfaces openvpn vtun10 encryption cipher 'aes256'
set interfaces openvpn vtun10 hash 'sha512'
set interfaces openvpn vtun10 mode 'client'
set interfaces openvpn vtun10 persistent-tunnel
set interfaces openvpn vtun10 protocol 'udp'
set interfaces openvpn vtun10 remote-host '198.51.100.254'
set interfaces openvpn vtun10 remote-port '1194'
set interfaces openvpn vtun10 tls ca-certificate 'OVPN-CA'
set interfaces openvpn vtun10 tls certificate 'CLIENT'
```


## Monitoring

If the client is connected successfully you can check the status

```none
vyos@ovpn-server:~$ show openvpn server
OpenVPN status on vtun10

Client CN    Remote Host         Tunnel IP    Local Host           TX bytes    RX bytes    Connected Since
-----------  ------------------  -----------  -------------------  ----------  ----------  -------------------
client       198.51.100.1:55150  10.23.1.6    198.51.100.254:1194  4.7 KB      4.7 KB      2023-05-11 12:47:11
```
