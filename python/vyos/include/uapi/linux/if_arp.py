# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# ARP protocol HARDWARE identifiers
ARPHRD_NETROM = 0        # from KA9Q: NET/ROM pseudo
ARPHRD_ETHER = 1         # Ethernet 10Mbps
ARPHRD_EETHER = 2        # Experimental Ethernet
ARPHRD_AX25 = 3          # AX.25 Level 2
ARPHRD_PRONET = 4        # PROnet token ring
ARPHRD_CHAOS = 5         # Chaosnet
ARPHRD_IEEE802 = 6       # IEEE 802.2 Ethernet/TR/TB
ARPHRD_ARCNET = 7        # ARCnet
ARPHRD_APPLETLK = 8      # APPLEtalk
ARPHRD_DLCI = 15         # Frame Relay DLCI
ARPHRD_ATM = 19          # ATM
ARPHRD_METRICOM = 23     # Metricom STRIP (new IANA id)
ARPHRD_IEEE1394 = 24     # IEEE 1394 IPv4 - RFC 2734
ARPHRD_EUI64 = 27        # EUI-64
ARPHRD_INFINIBAND = 32   # InfiniBand

# Dummy types for non-ARP hardware
ARPHRD_SLIP = 256
ARPHRD_CSLIP = 257
ARPHRD_SLIP6 = 258
ARPHRD_CSLIP6 = 259
ARPHRD_RSRVD = 260       # Notional KISS type
ARPHRD_ADAPT = 264
ARPHRD_ROSE = 270
ARPHRD_X25 = 271         # CCITT X.25
ARPHRD_HWX25 = 272       # Boards with X.25 in firmware
ARPHRD_CAN = 280         # Controller Area Network
ARPHRD_MCTP = 290
ARPHRD_PPP = 512
ARPHRD_CISCO = 513       # Cisco HDLC
ARPHRD_HDLC = ARPHRD_CISCO  # Alias for CISCO
ARPHRD_LAPB = 516        # LAPB
ARPHRD_DDCMP = 517       # Digital's DDCMP protocol
ARPHRD_RAWHDLC = 518     # Raw HDLC
ARPHRD_RAWIP = 519       # Raw IP

ARPHRD_TUNNEL = 768      # IPIP tunnel
ARPHRD_TUNNEL6 = 769     # IP6IP6 tunnel
ARPHRD_FRAD = 770        # Frame Relay Access Device
ARPHRD_SKIP = 771        # SKIP vif
ARPHRD_LOOPBACK = 772    # Loopback device
ARPHRD_LOCALTLK = 773    # Localtalk device
ARPHRD_FDDI = 774        # Fiber Distributed Data Interface
ARPHRD_BIF = 775         # AP1000 BIF
ARPHRD_SIT = 776         # sit0 device - IPv6-in-IPv4
ARPHRD_IPDDP = 777       # IP over DDP tunneller
ARPHRD_IPGRE = 778       # GRE over IP
ARPHRD_PIMREG = 779      # PIMSM register interface
ARPHRD_HIPPI = 780       # High Performance Parallel Interface
ARPHRD_ASH = 781         # Nexus 64Mbps Ash
ARPHRD_ECONET = 782      # Acorn Econet
ARPHRD_IRDA = 783        # Linux-IrDA
ARPHRD_FCPP = 784        # Point to point fibrechannel
ARPHRD_FCAL = 785        # Fibrechannel arbitrated loop
ARPHRD_FCPL = 786        # Fibrechannel public loop
ARPHRD_FCFABRIC = 787    # Fibrechannel fabric

ARPHRD_IEEE802_TR = 800  # Magic type ident for TR
ARPHRD_IEEE80211 = 801   # IEEE 802.11
ARPHRD_IEEE80211_PRISM = 802  # IEEE 802.11 + Prism2 header
ARPHRD_IEEE80211_RADIOTAP = 803  # IEEE 802.11 + radiotap header
ARPHRD_IEEE802154 = 804
ARPHRD_IEEE802154_MONITOR = 805  # IEEE 802.15.4 network monitor

ARPHRD_PHONET = 820      # PhoNet media type
ARPHRD_PHONET_PIPE = 821 # PhoNet pipe header
ARPHRD_CAIF = 822        # CAIF media type
ARPHRD_IP6GRE = 823      # GRE over IPv6
ARPHRD_NETLINK = 824     # Netlink header
ARPHRD_6LOWPAN = 825     # IPv6 over LoWPAN
ARPHRD_VSOCKMON = 826    # Vsock monitor header

ARPHRD_VOID = 0xFFFF     # Void type, nothing is known
ARPHRD_NONE = 0xFFFE     # Zero header length

# ARP protocol opcodes
ARPOP_REQUEST = 1        # ARP request
ARPOP_REPLY = 2          # ARP reply
ARPOP_RREQUEST = 3       # RARP request
ARPOP_RREPLY = 4         # RARP reply
ARPOP_InREQUEST = 8      # InARP request
ARPOP_InREPLY = 9        # InARP reply
ARPOP_NAK = 10           # (ATM)ARP NAK

ARPHRD_TO_NAME = {
    ARPHRD_NETROM: "netrom",
    ARPHRD_ETHER: "ether",
    ARPHRD_EETHER: "eether",
    ARPHRD_AX25: "ax25",
    ARPHRD_PRONET: "pronet",
    ARPHRD_CHAOS: "chaos",
    ARPHRD_IEEE802: "ieee802",
    ARPHRD_ARCNET: "arcnet",
    ARPHRD_APPLETLK: "atalk",
    ARPHRD_DLCI: "dlci",
    ARPHRD_ATM: "atm",
    ARPHRD_METRICOM: "metricom",
    ARPHRD_IEEE1394: "ieee1394",
    ARPHRD_INFINIBAND: "infiniband",
    ARPHRD_SLIP: "slip",
    ARPHRD_CSLIP: "cslip",
    ARPHRD_SLIP6: "slip6",
    ARPHRD_CSLIP6: "cslip6",
    ARPHRD_RSRVD: "rsrvd",
    ARPHRD_ADAPT: "adapt",
    ARPHRD_ROSE: "rose",
    ARPHRD_X25: "x25",
    ARPHRD_HWX25: "hwx25",
    ARPHRD_CAN: "can",
    ARPHRD_PPP: "ppp",
    ARPHRD_HDLC: "hdlc",
    ARPHRD_LAPB: "lapb",
    ARPHRD_DDCMP: "ddcmp",
    ARPHRD_RAWHDLC: "rawhdlc",
    ARPHRD_TUNNEL: "ipip",
    ARPHRD_TUNNEL6: "tunnel6",
    ARPHRD_FRAD: "frad",
    ARPHRD_SKIP: "skip",
    ARPHRD_LOOPBACK: "loopback",
    ARPHRD_LOCALTLK: "ltalk",
    ARPHRD_FDDI: "fddi",
    ARPHRD_BIF: "bif",
    ARPHRD_SIT: "sit",
    ARPHRD_IPDDP: "ip/ddp",
    ARPHRD_IPGRE: "gre",
    ARPHRD_PIMREG: "pimreg",
    ARPHRD_HIPPI: "hippi",
    ARPHRD_ASH: "ash",
    ARPHRD_ECONET: "econet",
    ARPHRD_IRDA: "irda",
    ARPHRD_FCPP: "fcpp",
    ARPHRD_FCAL: "fcal",
    ARPHRD_FCPL: "fcpl",
    ARPHRD_FCFABRIC: "fcfb0",
    ARPHRD_FCFABRIC+1: "fcfb1",
    ARPHRD_FCFABRIC+2: "fcfb2",
    ARPHRD_FCFABRIC+3: "fcfb3",
    ARPHRD_FCFABRIC+4: "fcfb4",
    ARPHRD_FCFABRIC+5: "fcfb5",
    ARPHRD_FCFABRIC+6: "fcfb6",
    ARPHRD_FCFABRIC+7: "fcfb7",
    ARPHRD_FCFABRIC+8: "fcfb8",
    ARPHRD_FCFABRIC+9: "fcfb9",
    ARPHRD_FCFABRIC+10: "fcfb10",
    ARPHRD_FCFABRIC+11: "fcfb11",
    ARPHRD_FCFABRIC+12: "fcfb12",
    ARPHRD_IEEE802_TR: "tr",
    ARPHRD_IEEE80211: "ieee802.11",
    ARPHRD_IEEE80211_PRISM: "ieee802.11/prism",
    ARPHRD_IEEE80211_RADIOTAP: "ieee802.11/radiotap",
    ARPHRD_IEEE802154: "ieee802.15.4",
    ARPHRD_IEEE802154_MONITOR: "ieee802.15.4/monitor",
    ARPHRD_PHONET: "phonet",
    ARPHRD_PHONET_PIPE: "phonet_pipe",
    ARPHRD_CAIF: "caif",
    ARPHRD_IP6GRE: "gre6",
    ARPHRD_NETLINK: "netlink",
    ARPHRD_6LOWPAN: "6lowpan",
    ARPHRD_NONE: "none",
    ARPHRD_VOID: "void",
}