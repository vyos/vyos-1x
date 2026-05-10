:lastproofread: 2026-01-12

.. _user_management:

#####################
Login/user management
#####################

The default VyOS user account (``vyos``), as well as newly created user accounts,
possess full system configuration privileges. These accounts are granted sudo 
privileges, allowing them to execute commands as the root user.

VyOS supports both local authentication and remote authentication via 
:abbr:`RADIUS (Remote Authentication Dial-In User Service)`/ :abbr:`TACACS+ 
(Terminal Access Controller Access-Control System)`.
 

Local authentication
====================

.. cfgcmd:: set system login user <name> full-name "<string>"

   **Configure the real name or description for a system user.**

   If the description includes spaces, enclose ``<string>`` in double quotes.

   If the user ``<name>`` already exists, the command updates the current 
   description. If not, it creates a new user with the specified description.

.. cfgcmd:: set system login user <name> authentication plaintext-password
   <password>

   **Configure a password for a system user.** 

   Enter the password in plaintext. Upon ``commit``, VyOS hashes the password for 
   secure storage and removes the plaintext value. 

   If the user ``<name>`` already exists, the command updates the current password. 
   If not, it creates a new user with the specified plaintext password. 
  
.. cfgcmd:: set system login user <name> authentication encrypted-password
   <password>

   **Configure a pre-encrypted password for a system user.** 

   Enter the password in its hashed format. Upon ``commit``, VyOS stores this value 
   directly without modification. 

   If the user ``<name>`` already exists, the command updates the current password. 
   If not, it creates a new user with the specified pre-encrypted password.

.. cfgcmd:: set system login user <name> authentication principal <principal>

   **Configure an SSH certificate principal for a system user.** 

   Enter the principal (a string included in the user's signed SSH certificate). 
   Upon ``commit``, VyOS stores this mapping, allowing the user to log in if the 
   certificate they present contains this principal. 

   If the user ``<name>`` already exists, the command updates the principal. If not, 
   it creates a new user linked to the specified principal.

   **If not configured**, the principal defaults to ``<name>``.

.. cfgcmd:: set system login user <name> disable

   **Disable a system user account.**

   VyOS locks the account, preventing the user from logging in.

.. _ssh_key_based_authentication:


Key-based authentication
========================

Key-based authentication is the recommended method for securing SSH access in 
VyOS. It uses a **public/private key pair** to verify user identity without 
requiring a password. To authorize access, you assign **SSH public keys** to 
user accounts on the router, while SSH private keys remain on local devices. 
VyOS allows assigning multiple SSH public keys to a single user account, which 
is useful for accessing a router from different devices.

Generate the key pair
^^^^^^^^^^^^^^^^^^^^^

Generate an SSH key pair on your **local machine** using the ``ssh-keygen`` 
command. This creates two files:

* **Private key** (e.g., ``id_rsa``): Remains on your local machine and must 
  never be shared.
* **Public key** (e.g., ``id_rsa.pub``): Is used to configure the VyOS user 
  account. By default, it is saved to ``~/.ssh/id_rsa.pub``. 

Each SSH public key consists of three parts, separated by spaces:

* **Encryption algorithm type:** ``ssh-rsa``, ``ssh-ed25519``, etc.
* **Key:** The actual data (a long string beginning with ``AAAA...``).
* **Comment:** An identifier for your reference (e.g., ``user@host``).

Only the encryption algorithm type and key parts are required to 
configure the authorization entry in VyOS. The comment part is optional. 

.. seealso:: :ref:`SSH operation <ssh_operation>`

.. warning:: SSH key strings are long. When copying and pasting, ensure your 
   terminal does not insert line breaks. The key must be entered as a **single 
   line** to function correctly.


Configure the router
^^^^^^^^^^^^^^^^^^^^
 
To configure SSH public key authentication for a user account, run the 
following two commands using the same ``<identifier>``:

.. cfgcmd:: set system login user <username> authentication public-keys
   <identifier> key <key>

   **Configure the SSH public key for the user account.** 

   * ``<identifier>``: A unique label that identifies this specific key entry.

   * ``<key>``: The actual string of characters from your public key. 

.. cfgcmd:: set system login user <username> authentication public-keys
   <identifier> type <type>

   **Configure the SSH key's encryption type.**
 
   The following encryption algorithm types are available:

   * ``ecdsa-sha2-nistp256``
   * ``ecdsa-sha2-nistp384``
   * ``ecdsa-sha2-nistp521``
   * ``ssh-dss``
   * ``ssh-ed25519``
   * ``ssh-rsa``

   .. note:: To assign multiple SSH public keys to a user account, repeat the 
      commands above with a unique identifier for each key.

.. cfgcmd:: set system login user <username> authentication public-keys
   <identifier> options <options>

   **Configure specific restrictions or behaviors for an SSH public key.**

   ``<options>``: A string of comma-separated values that define permissions 
   or restrictions for this key.

   The command accepts standard OpenSSH options listed in the router's 
   ``~/.ssh/authorized_keys`` file.

   To include a ``"`` character in the options string, use ``&quot;``.

   For example, to restrict allowed source IP addresses for an SSH public key, 
   use: ``from=&quot;10.0.0.0/24&quot;``.

OTP-based MFA
=============
VyOS lets you enhance user access security by enabling :abbr:`OTP (One-time 
password)`-based :abbr:`MFA (Multi-factor Authentication)` for individual 
users. Users with :abbr:`OTP (One-time password)`-based :abbr:`MFA 
(Multi-factor Authentication)` must enter a valid :abbr:`OTP (One-time 
password)` along with their password at login. Users without :abbr:`OTP 
(One-time password)`-based :abbr:`MFA (Multi-factor Authentication)` use 
standard authentication.

.. cfgcmd:: set system login user <username> authentication otp key <key>

   **Configure** :abbr:`OTP (One-time password)`**-based** :abbr:`MFA 
   (Multi-factor Authentication)` **for a user.**

   ``<key>``: A Base32-encoded secret key. This key must be added to the user's 
   authenticator app to generate valid :abbr:`OTPs (One-time passwords)`.

   **When configured**, the user is required to enter their password followed by 
   a valid OTP for all subsequent logins.

OTP settings
^^^^^^^^^^^^

.. cfgcmd:: set system login user <username> authentication otp rate-limit <limit>
 
   **Configure the number of** :abbr:`OTP (One-time password)` **authentication 
   attempts allowed within a specified time period.**

   If this limit is exceeded, the user is temporarily blocked.

   The default value is 3 attempts. The valid range is 1 to 10 attempts.

.. cfgcmd:: set system login user <username> authentication otp rate-time <seconds>
   
   **Configure the time period, in seconds, for tracking** :abbr:`OTP (One-time 
   password)` **authentication attempts.** 

   The default value is 30 seconds. The valid range is 1 to 600 seconds.

.. cfgcmd:: set system login user <username> authentication otp window-size <size>
   
   **Configure the** :abbr:`OTP (One-time password)` **window size for a user.**

   The :abbr:`OTP (One-time password)` window size defines the number of 
   concurrently valid :abbr:`OTPs (One-time passwords)` that the authentication 
   server accepts. This setting assumes a new token is generated every 30 seconds.

   The default value is 3. This permits 3 concurrent codes: the code for the 
   current 30-second interval, the preceding code, and the following code. This 
   allows up to 30 seconds of time skew between the authentication server and 
   client.

   If the window size is increased to 17, the system permits 17 concurrent codes 
   (the current code, the 8 preceding codes, and the 8 following codes). This 
   allows for a time skew of up to 4 minutes.

   The valid range is 1 to 21.

Generate an OTP-key 
^^^^^^^^^^^^^^^^^^^

Use the following command to generate an OTP key:

.. cfgcmd:: generate system login username <username> otp-key hotp-time
   rate-limit <1-10> rate-time <15-600> window-size <1-21>

Key generation example:

.. code-block:: none

   vyos@vyos:~$ generate system login username otptester otp-key hotp-time rate-limit 2 rate-time 20 window-size 5
   # You can share it with the user, he just needs to scan the QR in his OTP app
   # username:  otptester
   # OTP KEY:  J5A64ERPMGJOZXY6FMHHLKXKANNI6TCY
   # OTP URL:  otpauth://totp/otptester@vyos?secret=J5A64ERPMGJOZXY6FMHHLKXKANNI6TCY&digits=6&period=30
   █████████████████████████████████████████████
   █████████████████████████████████████████████
   ████ ▄▄▄▄▄ █▀█ █▄   ▀▄▀▄█▀▄  ▀█▀ █ ▄▄▄▄▄ ████
   ████ █   █ █▀▀▀█ ▄▀ █▄▀ ▀▄ ▄ ▀  ▄█ █   █ ████
   ████ █▄▄▄█ █▀ █▀▀██▄▄ █ █ ██ ▀▄▀ █ █▄▄▄█ ████
   ████▄▄▄▄▄▄▄█▄▀ ▀▄█ █ ▀ █ █ █ █▄█▄█▄▄▄▄▄▄▄████
   ████ ▄   █▄ ▄ ▀▄▀▀▀▀▄▀▄▀▄▄▄▀▀▄▄▄  █ █▄█ █████
   ████▄▄ ██▀▄▄▄▀▀█▀ ▄ ▄▄▄ ▄▀ ▀ █ ▄ ▄ ██▄█  ████
   █████▄  ██▄▄▀█▄█▄█▄ ▀█▄▀▄ ▀█▀▄ █▄▄▄ ▄   ▄████
   ████▀▀▄   ▄█▀▄▀ ▄█▀█▀▄▄▄▀█▄ ██▄▄▄  ▀█ █  ████
   ████ ▄▀▄█▀▄▄█▀▀▄▀▀▀▀█ ▄▀▄▀ ▄█ ▀▄  ▄ ▄▀ █▄████
   ████▄ ██ ▀▄▀▀ ▄█▀ ▄ ██ ▀█▄█ ▄█ ▄ ▀▄   ▄▄ ████
   ████▄█▀▀▄ ▄▄ █▄█▄█▄ █▄▄▀▄▄▀▀▄▄██▀ ▄▀▄▄ ▀▄████
   ████▀▄▀ ▄ ▄▀█ ▄ ▄█▀ █  ▀▄▄  ▄█▀ ▄▄   ▀▄▄ ████
   ████  ▀███▄ █▄█▄▀▀▀▀▄ ▄█▄▄▀ ▀███ ▄▄█▄▄  ▄████
   ████ ███▀ ▄▄▀▀██▀ ▄▀▄█▄▄▄ ██▄▄▀▄▀  ███▄ ▄████
   ████▄████▄▄▄▀▄ █▄█▄▀▄▄▄▄██▀ ▄▀ ▄ ▄▄▄ █▄▄█████
   ████ ▄▄▄▄▄ █▄▄▄ ▄█▀█▀▀▀▀█▀█▀ █▄█ █▄█ ▄█  ████
   ████ █   █ █ ██▄▀▀▀▀▄▄▄▀ ▄▄▄  ▀ ▄    ▄ ▄▄████
   ████ █▄▄▄█ █ ▀▀█▀ ▄▄█ █▄▄██▀▀█▀ █▄▀▄██▄█ ████
   ████▄▄▄▄▄▄▄█▄█▄█▄█▄▄▄▄▄█▄▄▄█▄██████▄██▄▄▄████
   █████████████████████████████████████████████
   █████████████████████████████████████████████
   # To add this OTP key to configuration, run the following commands:
   set system login user otptester authentication otp key 'J5A64ERPMGJOZXY6FMHHLKXKANNI6TCY'
   set system login user otptester authentication otp rate-limit '2'
   set system login user otptester authentication otp rate-time '20'
   set system login user otptester authentication otp window-size '5'

Display the OTP key for a user
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the following command to display the :abbr:`OTP (One-time password)` 
key for a user:

.. cfgcmd:: sh system login authentication user <username> otp
   <full | key-b32 | qrcode | uri>

Example:

.. code-block:: none

   vyos@vyos:~$ sh system login authentication user otptester otp full
   # You can share the OTP key with the user. They just need to scan the QR in their OTP app.
   # username: otptester
   # OTP KEY: J5A64ERPMGJOZXY6FMHHLKXKANNI6TCY
   # OTP URL: otpauth://totp/otptester@vyos?secret=J5A64ERPMGJOZXY6FMHHLKXKANNI6TCY&digits=6&period=30
   █████████████████████████████████████████████
   █████████████████████████████████████████████
   ████ ▄▄▄▄▄ █▀█ █▄   ▀▄▀▄█▀▄  ▀█▀ █ ▄▄▄▄▄ ████
   ████ █   █ █▀▀▀█ ▄▀ █▄▀ ▀▄ ▄ ▀  ▄█ █   █ ████
   ████ █▄▄▄█ █▀ █▀▀██▄▄ █ █ ██ ▀▄▀ █ █▄▄▄█ ████
   ████▄▄▄▄▄▄▄█▄▀ ▀▄█ █ ▀ █ █ █ █▄█▄█▄▄▄▄▄▄▄████
   ████ ▄   █▄ ▄ ▀▄▀▀▀▀▄▀▄▀▄▄▄▀▀▄▄▄  █ █▄█ █████
   ████▄▄ ██▀▄▄▄▀▀█▀ ▄ ▄▄▄ ▄▀ ▀ █ ▄ ▄ ██▄█  ████
   █████▄  ██▄▄▀█▄█▄█▄ ▀█▄▀▄ ▀█▀▄ █▄▄▄ ▄   ▄████
   ████▀▀▄   ▄█▀▄▀ ▄█▀█▀▄▄▄▀█▄ ██▄▄▄  ▀█ █  ████
   ████ ▄▀▄█▀▄▄█▀▀▄▀▀▀▀█ ▄▀▄▀ ▄█ ▀▄  ▄ ▄▀ █▄████
   ████▄ ██ ▀▄▀▀ ▄█▀ ▄ ██ ▀█▄█ ▄█ ▄ ▀▄   ▄▄ ████
   ████▄█▀▀▄ ▄▄ █▄█▄█▄ █▄▄▀▄▄▀▀▄▄██▀ ▄▀▄▄ ▀▄████
   ████▀▄▀ ▄ ▄▀█ ▄ ▄█▀ █  ▀▄▄  ▄█▀ ▄▄   ▀▄▄ ████
   ████  ▀███▄ █▄█▄▀▀▀▀▄ ▄█▄▄▀ ▀███ ▄▄█▄▄  ▄████
   ████ ███▀ ▄▄▀▀██▀ ▄▀▄█▄▄▄ ██▄▄▀▄▀  ███▄ ▄████
   ████▄████▄▄▄▀▄ █▄█▄▀▄▄▄▄██▀ ▄▀ ▄ ▄▄▄ █▄▄█████
   ████ ▄▄▄▄▄ █▄▄▄ ▄█▀█▀▀▀▀█▀█▀ █▄█ █▄█ ▄█  ████
   ████ █   █ █ ██▄▀▀▀▀▄▄▄▀ ▄▄▄  ▀ ▄    ▄ ▄▄████
   ████ █▄▄▄█ █ ▀▀█▀ ▄▄█ █▄▄██▀▀█▀ █▄▀▄██▄█ ████
   ████▄▄▄▄▄▄▄█▄█▄█▄█▄▄▄▄▄█▄▄▄█▄██████▄██▄▄▄████
   █████████████████████████████████████████████
   █████████████████████████████████████████████
   # To add this OTP key to configuration, run the following commands:
   set system login user otptester authentication otp key 'J5A64ERPMGJOZXY6FMHHLKXKANNI6TCY'
   set system login user otptester authentication otp rate-limit '2'
   set system login user otptester authentication otp rate-time '20'
   set system login user otptester authentication otp window-size '5'

Once :abbr:`OTP (One-time password)`-based :abbr:`MFA (Multi-factor 
Authentication)` is configured for a user account, this user must enter their 
standard password followed by the current 6-digit OTP code at login. For 
example, if the user's password is ``vyosrocks`` and the OTP is ``817454``, they 
should enter ``vyosrocks817454``.


RADIUS authentication
=====================

For large-scale deployments, managing individual user accounts across multiple 
VyOS instances is inefficient. VyOS supports centralized authentication via 
:abbr:`RADIUS (Remote Authentication Dial-In User Service)`, consolidating user 
account management on a single backend server.

Configuration
^^^^^^^^^^^^^

.. cfgcmd:: set system login radius server <address> key <secret>

   **Configure the** :abbr:`RADIUS (Remote Authentication Dial-In User Service)` 
   **server's IP address and shared secret.**

   The shared secret is used to verify the router's identity and to encrypt user 
   passwords during authentication.

   You can configure multiple :abbr:`RADIUS (Remote Authentication Dial-In User 
   Service)` servers. 

.. cfgcmd:: set system login radius server <address> port <port>

   **Configure the UDP port for communication with the** :abbr:`RADIUS (Remote 
   Authentication Dial-In User Service)` **server.**

   The default port is 1812.

.. cfgcmd:: set system login radius server <address> disable

   **Disable a** :abbr:`RADIUS (Remote Authentication Dial-In User Service)` 
   **server from the authentication process.** 

   Disabling a specific :abbr:`RADIUS (Remote Authentication Dial-In User 
   Service)` server doesn’t remove its configuration settings (the server's IP 
   address and shared secret).

.. cfgcmd:: set system login radius server <address> timeout <timeout>

   Configure the duration, in seconds, that the VyOS router waits for a 
   response from the :abbr:`RADIUS (Remote Authentication Dial-In User Service)` 
   server after sending an authentication request.

   If the server does not respond within this timeframe, the VyOS router tries to 
   connect to another configured server or falls back to local authentication.

.. cfgcmd:: set system login radius source-address <address>

   **Configure the source IP address the router uses for** :abbr:`RADIUS (Remote 
   Authentication Dial-In User Service)` **authentication requests.**

   A consistent source IP address is recommended as RADIUS servers typically 
   accept requests only from known, trusted IP addresses.

   If not explicitly defined, the router uses the current egress interface 
   address, which may change (e.g., due to a link outage), causing authentication 
   failures.

.. cfgcmd:: set system login radius vrf <name>

   **Configure the router to send all** :abbr:`RADIUS (Remote Authentication 
   Dial-In User Service)` **authentication requests via a specific VRF.** 

   By default, :abbr:`RADIUS (Remote Authentication Dial-In User Service)` 
   authentication requests are sent via the global routing table. 

Configuration example
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

  set system login radius server 192.168.0.2 key 'test-vyos'
  set system login radius server 192.168.0.2 port '1812'
  set system login radius server 192.168.0.2 timeout '5'
  set system login radius source-address '192.168.0.1'


If communication with the :abbr:`RADIUS (Remote Authentication Dial-In User 
Service)` server fails, the router falls back to local user authentication. 
During this process, users may experience a login delay while the system waits 
for the :abbr:`RADIUS (Remote Authentication Dial-In User Service)` request to 
time out. This delay depends on the configured `timeout` value.   

.. hint:: To grant administrative privileges to :abbr:`RADIUS (Remote 
   Authentication Dial-In User Service)`-authenticated users, the server must 
   return the Cisco-AV-Pair attribute set to ``shell:priv-lvl=15``. Otherwise, users 
   receive standard privileges and cannot perform configuration tasks.

TACACS+ authentication
======================

In addition to :abbr:`RADIUS (Remote Authentication Dial-In User Service)`, 
VyOS supports :abbr:`TACACS+ (Terminal Access Controller Access Control 
System)`, which is commonly used in large enterprise environments. 

Unlike :abbr:`RADIUS (Remote Authentication Dial-In User Service)`, 
:abbr:`TACACS+ (Terminal Access Controller Access Control System)` separates 
Authentication, Authorization, and Accounting (AAA) into independent processes 
and encrypts the entire packet body for enhanced security. 

:abbr:`TACACS+ (Terminal Access Controller Access Control System)` is defined 
in :rfc:`8907`.

.. _TACACS Configuration:

Configuration
^^^^^^^^^^^^^

.. cfgcmd:: set system login tacacs server <address> key <secret>

   **Configure the** :abbr:`TACACS+ (Terminal Access Controller Access Control 
   System)` **server IP address and shared secret.**

   Unlike :abbr:`RADIUS (Remote Authentication Dial-In User Service)`, which 
   encrypts only passwords, :abbr:`TACACS+ (Terminal Access Controller Access 
   Control System)` encrypts the entire packet body for enhanced security.

   You can configure multiple :abbr:`TACACS+ (Terminal Access Controller Access 
   Control System)` servers.

.. cfgcmd:: set system login tacacs server <address> port <port>

   **Configure the TCP port for communication with the** :abbr:`TACACS+ (Terminal 
   Access Controller Access Control System)` **server.**

   The default port is 49.

.. cfgcmd:: set system login tacacs server <address> disable

   **Disable a** :abbr:`TACACS+ (Terminal Access Controller Access Control 
   System)` **server from the authentication process.** 

   Disabling a specific :abbr:`TACACS+ (Terminal Access Controller Access Control 
   System)` server doesn’t remove its configuration settings (the server's IP 
   address and shared secret).

.. cfgcmd:: set system login tacacs server <address> timeout <timeout>

   Configure the duration, in seconds, that the VyOS router waits for a 
   response from the :abbr:`TACACS+ (Terminal Access Controller Access 
   Control System)` server after sending an authentication request.

   If the server does not respond within this timeframe, the VyOS router tries 
   to connect to another configured server or falls back to local authentication.

.. cfgcmd:: set system login tacacs source-address <address>

   **Configure the source IP address the router uses for** 
   :abbr:`TACACS+ (Terminal Access Controller Access Control System)` 
   **authentication requests.**

   A consistent source IP address is recommended as :abbr:`TACACS+ (Terminal 
   Access Controller Access Control System)` servers typically accept requests 
   only from known, trusted IP addresses.

   If not explicitly defined, the router uses the current egress interface address, 
   which may change (e.g., due to a link outage), causing authentication failures.

.. cfgcmd:: set system login tacacs vrf <name>

   Configure the router to send all :abbr:`TACACS+ (Terminal Access Controller 
   Access Control System)` authentication requests via a specific VRF. 

   By default, :abbr:`TACACS+ (Terminal Access Controller Access Control System)` 
   authentication requests are sent via the global routing table. 

.. _login:tacacs_example:

Configuration example
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

  set system login tacacs server 192.168.0.2 key 'test-vyos'
  set system login tacacs server 192.168.0.2 port '49'
  set system login tacacs source-address '192.168.0.1'


If communication with the :abbr:`TACACS+ (Terminal Access Controller Access 
Control System)` server fails, the router falls back to local user 
authentication. 

Login banners
=============

VyOS allows you to configure **pre-login** and **post-login** banners. 
Pre-login banners are typically used for system identification, legal disclaimers, or security warnings 
displayed before authentication, while post-login banners provide system 
information or operational notices to users after login.

.. cfgcmd:: set system login banner pre-login <message>

   Configure a message to be shown to users before the ``username`` and ``password`` 
   prompts appear.

.. cfgcmd:: set system login banner post-login <message>

   Configure a message to be shown to users after successful authentication.

.. note:: Use ``\\n`` to insert line breaks in multi-line banner messages.

Login session limits
====================

.. cfgcmd:: set system login max-login-session <number>

   **Configure the maximum number of concurrent login sessions.**

.. note:: If you limit concurrent login sessions, you must also configure a 
   session ``<timeout>``. This clears inactive sessions and prevents blocking new 
   login attempts.

.. cfgcmd:: set system login timeout <timeout>

   **Configure the login session timeout, in seconds.** 

   Idle login sessions are terminated after this period.

Configuration examples
======================

Example 1: Multi-key SSH with MFA and source restrictions

In this configuration, ``User1`` and ``User2`` both use the vyos user account, 
each with a unique SSH key. ``User1`` is restricted to authentication from a 
single IP address.

For both users, password-based logins require :abbr:`OTP (One-time password)`
-based :abbr:`MFA (Multi-factor Authentication)`.

.. code-block:: none

  set system login user vyos authentication public-keys 'User1' key "AAAAB3Nz...KwEW"
  set system login user vyos authentication public-keys 'User1' type ssh-rsa
  set system login user vyos authentication public-keys 'User1' options "from=&quot;192.168.0.100&quot;"

  set system login user vyos authentication public-keys 'User2' key "AAAAQ39x...fbV3"
  set system login user vyos authentication public-keys 'User2' type ssh-rsa

  set system login user vyos authentication otp key OHZ3OJ7U2N25BK4G7SOFFJTZDTCFUUE2
  set system login user vyos authentication plaintext-password vyos


Example 2: Containerized :abbr:`TACACS+ (Terminal Access Controller Access Control System)`
deployment with redundancy.

In this configuration, the VyOS router hosts its own authentication 
infrastructure using two containerized :abbr:`TACACS+ (Terminal Access 
Controller Access Control System)` servers (``tacacs1`` and ``tacacs2``) on a 
private network for redundancy.

System logins are authenticated against credentials stored within these internal 
containers rather than the router's local user database.

First, download the image in operational mode:

.. code-block:: none

   add container image lfkeitel/tacacs_plus:latest

Next, configure the containers in configuration mode:

.. code-block:: none

   set container network tac-test prefix '100.64.0.0/24'

   set container name tacacs1 image 'lfkeitel/tacacs_plus:latest'
   set container name tacacs1 network tac-test address '100.64.0.11'

   set container name tacacs2 image 'lfkeitel/tacacs_plus:latest'
   set container name tacacs2 network tac-test address '100.64.0.12'

   set system login tacacs server 100.64.0.11 key 'tac_plus_key'
   set system login tacacs server 100.64.0.12 key 'tac_plus_key'

   commit

You can now log in via SSH or console using ``admin/admin`` credentials supplied 
by the container image.
