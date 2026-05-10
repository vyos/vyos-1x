.. _troubleshooting_ipsec:

######################################
Troubleshooting Site-to-Site VPN IPsec
######################################

.. TODO:: Convert raw command blocks in this file to cfgcmd/opcmd
   directives for command coverage tracking.

************
Introduction
************

This document describes the methodology to monitor and troubleshoot
Site-to-Site VPN IPsec.

Steps for troubleshooting problems with Site-to-Site VPN IPsec:
 1. Ping the remote site through the tunnel using the source and
    destination IPs included in the policy.
 2. Check connectivity between the routers using the ping command
    (if ICMP traffic is allowed).
 3. Check the IKE SAs' statuses.
 4. Check the IPsec SAs' statuses.
 5. Check logs to view debug messages.

**********************
Checking IKE SA Status
**********************

The next command shows IKE SAs' statuses.

.. stop_vyoslinter

.. code-block:: none

 vyos@vyos:~$ show vpn ike sa

 Peer ID / IP                            Local ID / IP
 ------------                            -------------
 192.168.1.2 192.168.1.2                 192.168.0.1 192.168.0.1

     State  IKEVer  Encrypt      Hash          D-H Group      NAT-T  A-Time  L-Time
     -----  ------  -------      ----          ---------      -----  ------  ------
     up     IKEv2   AES_CBC_128  HMAC_SHA1_96  MODP_2048      no     162     27023

This command shows the next information:
 - IKE SA status.
 - Selected IKE version.
 - Selected Encryption, Hash and Diffie-Hellman Group.
 - NAT-T.
 - ID and IP of both peers.
 - A-Time: established time, L-Time: time for next rekeying.

**************************
IPsec SA (CHILD SA) Status
**************************

The next commands show IPsec SAs' statuses.

.. code-block:: none

 vyos@vyos:~$ show vpn ipsec sa
 Connection     State    Uptime    Bytes In/Out    Packets In/Out    Remote address    Remote ID    Proposal
 -------------  -------  --------  --------------  ----------------  ----------------  -----------  ----------------------------------
 PEER-tunnel-1  up       16m30s    168B/168B       2/2               192.168.1.2       192.168.1.2  AES_CBC_128/HMAC_SHA1_96/MODP_2048

.. code-block:: none

 vyos@vyos:~$ show vpn ipsec sa detail
 PEER: #1, ESTABLISHED, IKEv2, 101275ac719d5a1b_i* 68ea4ec3bed3bf0c_r
   local  '192.168.0.1' @ 192.168.0.1[4500]
   remote '192.168.1.2' @ 192.168.1.2[4500]
   AES_CBC-128/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
   established 4054s ago, rekeying in 23131s
   PEER-tunnel-1: #2, reqid 1, INSTALLED, TUNNEL, ESP:AES_CBC-128/HMAC_SHA1_96/MODP_2048
     installed 1065s ago, rekeying in 1998s, expires in 2535s
     in  c5821882,    168 bytes,     2 packets,    81s ago
     out c433406a,    168 bytes,     2 packets,    81s ago
     local  10.0.0.0/24
     remote 10.0.1.0/24

These commands show the next information:
 - IPsec SA status.
 - Uptime and time for the next rekeing.
 - Amount of transferred data.
 - Remote and local ID and IP.
 - Selected Encryption, Hash and Diffie-Hellman Group.
 - Mode (tunnel or transport).
 - Remote and local prefixes which are use for policy.

There is a possibility to view the summarized information of SAs' status

.. code-block:: none

 vyos@vyos:~$ show vpn ipsec connections
 Connection     State    Type    Remote address    Local TS     Remote TS    Local id     Remote id    Proposal
 -------------  -------  ------  ----------------  -----------  -----------  -----------  -----------  ----------------------------------
 PEER           up       IKEv2   192.168.1.2       -            -            192.168.0.1  192.168.1.2  AES_CBC/128/HMAC_SHA1_96/MODP_2048
 PEER-tunnel-1  up       IPsec   192.168.1.2       10.0.0.0/24  10.0.1.0/24  192.168.0.1  192.168.1.2  AES_CBC/128/HMAC_SHA1_96/MODP_2048

**************************
Viewing Logs for Debugging
**************************

If IKE SAs or IPsec SAs are down, need to debug IPsec connectivity
using logs ``show log ipsec``

The next example of the successful IPsec connection initialization.

.. code-block:: none

 vyos@vyos:~$ show log ipsec
 Jun 20 14:29:47 charon[2428]: 02[NET] <PEER|1> received packet: from 192.168.1.2[500] to 192.168.0.1[500] (472 bytes)
 Jun 20 14:29:47 charon[2428]: 02[ENC] <PEER|1> parsed IKE_SA_INIT response 0 [ SA KE No N(NATD_S_IP) N(NATD_D_IP) N(FRAG_SUP) N(HASH_ALG) N(CHDLESS_SUP) N(MULT_AUTH) ]
 Jun 20 14:29:47 charon-systemd[2428]: received packet: from 192.168.1.2[500] to 192.168.0.1[500] (472 bytes)
 Jun 20 14:29:47 charon[2428]: 02[CFG] <PEER|1> selected proposal: IKE:AES_CBC_128/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
 Jun 20 14:29:47 charon-systemd[2428]: parsed IKE_SA_INIT response 0 [ SA KE No N(NATD_S_IP) N(NATD_D_IP) N(FRAG_SUP) N(HASH_ALG) N(CHDLESS_SUP) N(MULT_AUTH) ]
 Jun 20 14:29:47 charon-systemd[2428]: selected proposal: IKE:AES_CBC_128/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
 Jun 20 14:29:47 charon[2428]: 02[IKE] <PEER|1> authentication of '192.168.0.1' (myself) with pre-shared key
 Jun 20 14:29:47 charon-systemd[2428]: authentication of '192.168.0.1' (myself) with pre-shared key
 Jun 20 14:29:47 charon[2428]: 02[IKE] <PEER|1> establishing CHILD_SA PEER-tunnel-1{1}
 Jun 20 14:29:47 charon-systemd[2428]: establishing CHILD_SA PEER-tunnel-1{1}
 Jun 20 14:29:47 charon[2428]: 02[ENC] <PEER|1> generating IKE_AUTH request 1 [ IDi N(INIT_CONTACT) IDr AUTH SA TSi TSr N(MOBIKE_SUP) N(NO_ADD_ADDR) N(MULT_AUTH) N(EAP_ONLY) N(MSG_ID_SYN_SUP) ]
 Jun 20 14:29:47 charon-systemd[2428]: generating IKE_AUTH request 1 [ IDi N(INIT_CONTACT) IDr AUTH SA TSi TSr N(MOBIKE_SUP) N(NO_ADD_ADDR) N(MULT_AUTH) N(EAP_ONLY) N(MSG_ID_SYN_SUP) ]
 Jun 20 14:29:47 charon[2428]: 02[NET] <PEER|1> sending packet: from 192.168.0.1[4500] to 192.168.1.2[4500] (268 bytes)
 Jun 20 14:29:47 charon-systemd[2428]: sending packet: from 192.168.0.1[4500] to 192.168.1.2[4500] (268 bytes)
 Jun 20 14:29:47 charon[2428]: 13[NET] <PEER|1> received packet: from 192.168.1.2[4500] to 192.168.0.1[4500] (220 bytes)
 Jun 20 14:29:47 charon[2428]: 13[ENC] <PEER|1> parsed IKE_AUTH response 1 [ IDr AUTH SA TSi TSr N(MOBIKE_SUP) N(NO_ADD_ADDR) ]
 Jun 20 14:29:47 charon-systemd[2428]: received packet: from 192.168.1.2[4500] to 192.168.0.1[4500] (220 bytes)
 Jun 20 14:29:47 charon[2428]: 13[IKE] <PEER|1> authentication of '192.168.1.2' with pre-shared key successful
 Jun 20 14:29:47 charon-systemd[2428]: parsed IKE_AUTH response 1 [ IDr AUTH SA TSi TSr N(MOBIKE_SUP) N(NO_ADD_ADDR) ]
 Jun 20 14:29:47 charon[2428]: 13[IKE] <PEER|1> peer supports MOBIKE
 Jun 20 14:29:47 charon-systemd[2428]: authentication of '192.168.1.2' with pre-shared key successful
 Jun 20 14:29:47 charon[2428]: 13[IKE] <PEER|1> IKE_SA PEER[1] established between 192.168.0.1[192.168.0.1]...192.168.1.2[192.168.1.2]
 Jun 20 14:29:47 charon-systemd[2428]: peer supports MOBIKE
 Jun 20 14:29:47 charon[2428]: 13[IKE] <PEER|1> scheduling rekeying in 27703s
 Jun 20 14:29:47 charon-systemd[2428]: IKE_SA PEER[1] established between 192.168.0.1[192.168.0.1]...192.168.1.2[192.168.1.2]
 Jun 20 14:29:47 charon[2428]: 13[IKE] <PEER|1> maximum IKE_SA lifetime 30583s
 Jun 20 14:29:47 charon-systemd[2428]: scheduling rekeying in 27703s
 Jun 20 14:29:47 charon[2428]: 13[CFG] <PEER|1> selected proposal: ESP:AES_CBC_128/HMAC_SHA1_96/NO_EXT_SEQ
 Jun 20 14:29:47 charon-systemd[2428]: maximum IKE_SA lifetime 30583s
 Jun 20 14:29:47 charon-systemd[2428]: selected proposal: ESP:AES_CBC_128/HMAC_SHA1_96/NO_EXT_SEQ
 Jun 20 14:29:47 charon[2428]: 13[IKE] <PEER|1> CHILD_SA PEER-tunnel-1{1} established with SPIs cb94fb3f_i ca99c8a9_o and TS 10.0.0.0/24 === 10.0.1.0/24
 Jun 20 14:29:47 charon-systemd[2428]: CHILD_SA PEER-tunnel-1{1} established with SPIs cb94fb3f_i ca99c8a9_o and TS 10.0.0.0/24 === 10.0.1.0/24

************************
Troubleshooting Examples
************************

IKE PROPOSAL are Different
==========================

In this situation, IKE SAs can be down or not active.

.. code-block:: none

 vyos@vyos:~$ show vpn ike sa

The problem is in IKE phase (Phase 1). The next step is checking debug logs.

Responder Side:

.. code-block:: none

 Jun 23 07:36:33 charon[2440]: 01[CFG] <1> received proposals: IKE:AES_CBC_256/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
 Jun 23 07:36:33 charon-systemd[2440]: received proposals: IKE:AES_CBC_256/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
 Jun 23 07:36:33 charon[2440]: 01[CFG] <1> configured proposals: IKE:AES_CBC_128/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
 Jun 23 07:36:33 charon-systemd[2440]: configured proposals: IKE:AES_CBC_128/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
 Jun 23 07:36:33 charon[2440]: 01[IKE] <1> received proposals unacceptable
 Jun 23 07:36:33 charon-systemd[2440]: received proposals unacceptable
 Jun 23 07:36:33 charon[2440]: 01[ENC] <1> generating IKE_SA_INIT response 0 [ N(NO_PROP) ]

Initiator side:

.. code-block:: none

 Jun 23 07:36:32 charon-systemd[2444]: parsed IKE_SA_INIT response 0 [ N(NO_PROP) ]
 Jun 23 07:36:32 charon[2444]: 14[IKE] <PEER|1> received NO_PROPOSAL_CHOSEN notify error
 Jun 23 07:36:32 charon-systemd[2444]: received NO_PROPOSAL_CHOSEN notify error

The notification **NO_PROPOSAL_CHOSEN** means that the proposal mismatch.
On the Responder side there is concrete information where is mismatch.
Encryption **AES_CBC_128** is configured in IKE policy on the responder 
but **AES_CBC_256** is configured on the initiator side.

PSK Secret Mismatch
===================

In this situation, IKE SAs can be down or not active.

.. code-block:: none

 vyos@vyos:~$ show vpn ike sa

The problem is in IKE phase (Phase 1). The next step is checking debug logs.

Responder:

.. code-block:: none

 Jun 23 08:07:26 charon-systemd[2440]: tried 1 shared key for '192.168.1.2' - '192.168.0.1', but MAC mismatched
 Jun 23 08:07:26 charon[2440]: 13[ENC] <PEER|3> generating IKE_AUTH response 1 [ N(AUTH_FAILED) ]

Initiator side:

.. code-block:: none

 Jun 23 08:07:24 charon[2436]: 12[ENC] <PEER|1> parsed IKE_AUTH response 1 [ N(AUTH_FAILED) ]
 Jun 23 08:07:24 charon-systemd[2436]: parsed IKE_AUTH response 1 [ N(AUTH_FAILED) ]
 Jun 23 08:07:24 charon[2436]: 12[IKE] <PEER|1> received AUTHENTICATION_FAILED notify error
 Jun 23 08:07:24 charon-systemd[2436]: received AUTHENTICATION_FAILED notify error

The notification **AUTHENTICATION_FAILED** means that the authentication
is failed. There is a reason to check PSK on both side.

ESP Proposal Mismatch
=====================

The output of **show** commands shows us that IKE SA is established but
IPSec SA is not.

.. code-block:: none

 vyos@vyos:~$ show vpn ike sa
 Peer ID / IP                            Local ID / IP
 ------------                            -------------
 192.168.1.2 192.168.1.2                 192.168.0.1 192.168.0.1

     State  IKEVer  Encrypt      Hash          D-H Group      NAT-T  A-Time  L-Time
     -----  ------  -------      ----          ---------      -----  ------  ------
     up     IKEv2   AES_CBC_128  HMAC_SHA1_96  MODP_2048      no     158     26817

.. code-block:: none

 vyos@vyos:~$ show vpn ipsec sa
 Connection    State    Uptime    Bytes In/Out    Packets In/Out    Remote address    Remote ID    Proposal
 ------------  -------  --------  --------------  ----------------  ----------------  -----------  ----------

The next step is checking debug logs.

Initiator side:

.. code-block:: none

 Jun 23 08:16:10 charon[3789]: 13[NET] <PEER|1> received packet: from 192.168.1.2[500] to 192.168.0.1[500] (472 bytes)
 Jun 23 08:16:10 charon[3789]: 13[ENC] <PEER|1> parsed IKE_SA_INIT response 0 [ SA KE No N(NATD_S_IP) N(NATD_D_IP) N(FRAG_SUP) N(HASH_ALG) N(CHDLESS_SUP) N(MULT_AUTH) ]
 Jun 23 08:16:10 charon-systemd[3789]: received packet: from 192.168.1.2[500] to 192.168.0.1[500] (472 bytes)
 Jun 23 08:16:10 charon[3789]: 13[CFG] <PEER|1> selected proposal: IKE:AES_CBC_128/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
 Jun 23 08:16:10 charon-systemd[3789]: parsed IKE_SA_INIT response 0 [ SA KE No N(NATD_S_IP) N(NATD_D_IP) N(FRAG_SUP) N(HASH_ALG) N(CHDLESS_SUP) N(MULT_AUTH) ]
 Jun 23 08:16:10 charon-systemd[3789]: selected proposal: IKE:AES_CBC_128/HMAC_SHA1_96/PRF_HMAC_SHA1/MODP_2048
 Jun 23 08:16:10 charon[3789]: 13[IKE] <PEER|1> authentication of '192.168.0.1' (myself) with pre-shared key
 Jun 23 08:16:10 charon-systemd[3789]: authentication of '192.168.0.1' (myself) with pre-shared key
 Jun 23 08:16:10 charon[3789]: 13[IKE] <PEER|1> establishing CHILD_SA PEER-tunnel-1{1}
 Jun 23 08:16:10 charon-systemd[3789]: establishing CHILD_SA PEER-tunnel-1{1}
 Jun 23 08:16:10 charon[3789]: 13[ENC] <PEER|1> generating IKE_AUTH request 1 [ IDi N(INIT_CONTACT) IDr AUTH SA TSi TSr N(MOBIKE_SUP) N(NO_ADD_ADDR) N(MULT_AUTH) N(EAP_ONLY) N(MSG_ID_SYN_SUP) ]
 Jun 23 08:16:10 charon-systemd[3789]: generating IKE_AUTH request 1 [ IDi N(INIT_CONTACT) IDr AUTH SA TSi TSr N(MOBIKE_SUP) N(NO_ADD_ADDR) N(MULT_AUTH) N(EAP_ONLY) N(MSG_ID_SYN_SUP) ]
 Jun 23 08:16:10 charon[3789]: 13[NET] <PEER|1> sending packet: from 192.168.0.1[4500] to 192.168.1.2[4500] (268 bytes)
 Jun 23 08:16:10 charon-systemd[3789]: sending packet: from 192.168.0.1[4500] to 192.168.1.2[4500] (268 bytes)
 Jun 23 08:16:10 charon[3789]: 09[NET] <PEER|1> received packet: from 192.168.1.2[4500] to 192.168.0.1[4500] (140 bytes)
 Jun 23 08:16:10 charon-systemd[3789]: received packet: from 192.168.1.2[4500] to 192.168.0.1[4500] (140 bytes)
 Jun 23 08:16:10 charon[3789]: 09[ENC] <PEER|1> parsed IKE_AUTH response 1 [ IDr AUTH N(MOBIKE_SUP) N(NO_ADD_ADDR) N(NO_PROP) ]
 Jun 23 08:16:10 charon-systemd[3789]: parsed IKE_AUTH response 1 [ IDr AUTH N(MOBIKE_SUP) N(NO_ADD_ADDR) N(NO_PROP) ]
 Jun 23 08:16:10 charon[3789]: 09[IKE] <PEER|1> authentication of '192.168.1.2' with pre-shared key successful
 Jun 23 08:16:10 charon-systemd[3789]: authentication of '192.168.1.2' with pre-shared key successful
 Jun 23 08:16:10 charon[3789]: 09[IKE] <PEER|1> peer supports MOBIKE
 Jun 23 08:16:10 charon-systemd[3789]: peer supports MOBIKE
 Jun 23 08:16:10 charon[3789]: 09[IKE] <PEER|1> IKE_SA PEER[1] established between 192.168.0.1[192.168.0.1]...192.168.1.2[192.168.1.2]
 Jun 23 08:16:10 charon-systemd[3789]: IKE_SA PEER[1] established between 192.168.0.1[192.168.0.1]...192.168.1.2[192.168.1.2]
 Jun 23 08:16:10 charon[3789]: 09[IKE] <PEER|1> scheduling rekeying in 26975s
 Jun 23 08:16:10 charon-systemd[3789]: scheduling rekeying in 26975s
 Jun 23 08:16:10 charon[3789]: 09[IKE] <PEER|1> maximum IKE_SA lifetime 29855s
 Jun 23 08:16:10 charon-systemd[3789]: maximum IKE_SA lifetime 29855s
 Jun 23 08:16:10 charon[3789]: 09[IKE] <PEER|1> received NO_PROPOSAL_CHOSEN notify, no CHILD_SA built
 Jun 23 08:16:10 charon-systemd[3789]: received NO_PROPOSAL_CHOSEN notify, no CHILD_SA built
 Jun 23 08:16:10 charon[3789]: 09[IKE] <PEER|1> failed to establish CHILD_SA, keeping IKE_SA
 Jun 23 08:16:10 charon-systemd[3789]: failed to establish CHILD_SA, keeping IKE_SA

There are messages: **NO_PROPOSAL_CHOSEN** and
**failed to establish CHILD_SA** which refers that the problem is in
the IPsec(ESP) proposal mismatch.

The reason of this problem is showed on the responder side.

.. code-block:: none

 Jun 23 08:16:12 charon[2440]: 01[CFG] <PEER|5> received proposals: ESP:AES_CBC_256/HMAC_SHA1_96/NO_EXT_SEQ
 Jun 23 08:16:12 charon-systemd[2440]: received proposals: ESP:AES_CBC_256/HMAC_SHA1_96/NO_EXT_SEQ
 Jun 23 08:16:12 charon[2440]: 01[CFG] <PEER|5> configured proposals: ESP:AES_CBC_128/HMAC_SHA1_96/MODP_2048/NO_EXT_SEQ
 Jun 23 08:16:12 charon-systemd[2440]: configured proposals: ESP:AES_CBC_128/HMAC_SHA1_96/MODP_2048/NO_EXT_SEQ
 Jun 23 08:16:12 charon[2440]: 01[IKE] <PEER|5> no acceptable proposal found
 Jun 23 08:16:12 charon-systemd[2440]: no acceptable proposal found
 Jun 23 08:16:12 charon[2440]: 01[IKE] <PEER|5> failed to establish CHILD_SA, keeping IKE_SA

Encryption **AES_CBC_128** is configured in IKE policy on the responder but **AES_CBC_256**
is configured on the initiator side.

Prefixes in Policies Mismatch
=============================

As in previous situation, IKE SA is in up state but IPsec SA is not up.
According to logs we can see **TS_UNACCEPTABLE** notification. It means
that prefixes (traffic selectors) mismatch on both sides

Initiator:

.. code-block:: none

 Jun 23 14:13:17 charon[4996]: 11[IKE] <PEER|1> received TS_UNACCEPTABLE notify, no CHILD_SA built
 Jun 23 14:13:17 charon-systemd[4996]: maximum IKE_SA lifetime 29437s
 Jun 23 14:13:17 charon[4996]: 11[IKE] <PEER|1> failed to establish CHILD_SA, keeping IKE_SA
 Jun 23 14:13:17 charon-systemd[4996]: received TS_UNACCEPTABLE notify, no CHILD_SA built
 Jun 23 14:13:17 charon-systemd[4996]: failed to establish CHILD_SA, keeping IKE_SA

The reason of this problem is showed on the responder side.

.. code-block:: none

 Jun 23 14:13:19 charon[2440]: 01[IKE] <PEER|7> traffic selectors 10.0.2.0/24 === 10.0.0.0/24 unacceptable
 Jun 23 14:13:19 charon-systemd[2440]: traffic selectors 10.0.2.0/24 === 10.0.0.0/24 unacceptable
 Jun 23 14:13:19 charon[2440]: 01[IKE] <PEER|7> failed to establish CHILD_SA, keeping IKE_SA
 Jun 23 14:13:19 charon-systemd[2440]: failed to establish CHILD_SA, keeping IKE_SA
 Jun 23 14:13:19 charon[2440]: 01[ENC] <PEER|7> generating IKE_AUTH response 1 [ IDr AUTH N(MOBIKE_SUP) N(NO_ADD_ADDR) N(TS_UNACCEPT) ]
 Jun 23 14:13:19 charon-systemd[2440]: generating IKE_AUTH response 1 [ IDr AUTH N(MOBIKE_SUP) N(NO_ADD_ADDR) N(TS_UNACCEPT) ]

.. start_vyoslinter

Traffic selectors **10.0.2.0/24 === 10.0.0.0/24** are unacceptable on the
responder side.


