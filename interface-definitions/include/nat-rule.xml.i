<!-- include start from nat-rule.xml.i -->
<tagNode name="rule">
  <properties>
    <help>Rule number for NAT</help>
    <valueHelp>
      <format>u32:1-999999</format>
      <description>Number of NAT rule</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-999999"/>
    </constraint>
    <constraintErrorMessage>NAT rule number must be between 1 and 999999</constraintErrorMessage>
  </properties>
  <children>
    #include <include/generic-description.xml.i>
    <node name="destination">
      <properties>
        <help>NAT destination parameters</help>
      </properties>
      <children>
        #include <include/firewall/fqdn.xml.i>
        #include <include/nat-address.xml.i>
        #include <include/nat-port.xml.i>
        #include <include/firewall/source-destination-group.xml.i>
      </children>
    </node>
    #include <include/generic-disable-node.xml.i>
    #include <include/nat-exclude.xml.i>
    <node name="load-balance">
      <properties>
        <help>Apply NAT load balance</help>
      </properties>
      <children>
        #include <include/firewall/firewall-hashing-parameters.xml.i>
        #include <include/firewall/nat-balance.xml.i>
      </children>
    </node>
    #include <include/firewall/log.xml.i>
    <leafNode name="packet-type">
      <properties>
        <help>Packet type</help>
        <completionHelp>
          <list>broadcast host multicast other</list>
        </completionHelp>
        <valueHelp>
          <format>broadcast</format>
          <description>Match broadcast packet type</description>
        </valueHelp>
        <valueHelp>
          <format>host</format>
          <description>Match host packet type, addressed to local host</description>
        </valueHelp>
        <valueHelp>
          <format>multicast</format>
          <description>Match multicast packet type</description>
        </valueHelp>
        <valueHelp>
          <format>other</format>
          <description>Match packet addressed to another host</description>
        </valueHelp>
        <constraint>
          <regex>(broadcast|host|multicast|other)</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="protocol">
      <properties>
        <help>Protocol to NAT</help>
        <completionHelp>
          <list>all ip hopopt icmp igmp ggp ipencap st tcp egp igp pup udp tcp_udp hmp xns-idp rdp iso-tp4 dccp xtp ddp idpr-cmtp ipv6 ipv6-route ipv6-frag idrp rsvp gre esp ah skip ipv6-icmp ipv6-nonxt ipv6-opts rspf vmtp eigrp ospf ax.25 ipip etherip encap 99 pim ipcomp vrrp l2tp isis sctp fc mobility-header udplite mpls-in-ip manet hip shim6 wesp rohc</list>
        </completionHelp>
        <valueHelp>
          <format>all</format>
          <description>All IP protocols</description>
        </valueHelp>
        <valueHelp>
          <format>ip</format>
          <description>Internet Protocol, pseudo protocol number</description>
        </valueHelp>
        <valueHelp>
          <format>hopopt</format>
          <description>IPv6 Hop-by-Hop Option [RFC1883]</description>
        </valueHelp>
        <valueHelp>
          <format>icmp</format>
          <description>internet control message protocol</description>
        </valueHelp>
        <valueHelp>
          <format>igmp</format>
          <description>Internet Group Management</description>
        </valueHelp>
        <valueHelp>
          <format>ggp</format>
          <description>gateway-gateway protocol</description>
        </valueHelp>
        <valueHelp>
          <format>ipencap</format>
          <description>IP encapsulated in IP (officially IP)</description>
        </valueHelp>
        <valueHelp>
          <format>st</format>
          <description>ST datagram mode</description>
        </valueHelp>
        <valueHelp>
          <format>tcp</format>
          <description>transmission control protocol</description>
        </valueHelp>
        <valueHelp>
          <format>egp</format>
          <description>exterior gateway protocol</description>
        </valueHelp>
        <valueHelp>
          <format>igp</format>
          <description>any private interior gateway (Cisco)</description>
        </valueHelp>
        <valueHelp>
          <format>pup</format>
          <description>PARC universal packet protocol</description>
        </valueHelp>
        <valueHelp>
          <format>udp</format>
          <description>user datagram protocol</description>
        </valueHelp>
        <valueHelp>
          <format>tcp_udp</format>
          <description>Both TCP and UDP</description>
        </valueHelp>
        <valueHelp>
          <format>hmp</format>
          <description>host monitoring protocol</description>
        </valueHelp>
        <valueHelp>
          <format>xns-idp</format>
          <description>Xerox NS IDP</description>
        </valueHelp>
        <valueHelp>
          <format>rdp</format>
          <description>"reliable datagram" protocol</description>
        </valueHelp>
        <valueHelp>
          <format>iso-tp4</format>
          <description>ISO Transport Protocol class 4 [RFC905]</description>
        </valueHelp>
        <valueHelp>
          <format>dccp</format>
          <description>Datagram Congestion Control Prot. [RFC4340]</description>
        </valueHelp>
        <valueHelp>
          <format>xtp</format>
          <description>Xpress Transfer Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>ddp</format>
          <description>Datagram Delivery Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>idpr-cmtp</format>
          <description>IDPR Control Message Transport</description>
        </valueHelp>
        <valueHelp>
          <format>Ipv6</format>
          <description>Internet Protocol, version 6</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6-route</format>
          <description>Routing Header for IPv6</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6-frag</format>
          <description>Fragment Header for IPv6</description>
        </valueHelp>
        <valueHelp>
          <format>idrp</format>
          <description>Inter-Domain Routing Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>rsvp</format>
          <description>Reservation Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>gre</format>
          <description>General Routing Encapsulation</description>
        </valueHelp>
        <valueHelp>
          <format>esp</format>
          <description>Encap Security Payload [RFC2406]</description>
        </valueHelp>
        <valueHelp>
          <format>ah</format>
          <description>Authentication Header [RFC2402]</description>
        </valueHelp>
        <valueHelp>
          <format>skip</format>
          <description>SKIP</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6-icmp</format>
          <description>ICMP for IPv6</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6-nonxt</format>
          <description>No Next Header for IPv6</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6-opts</format>
          <description>Destination Options for IPv6</description>
        </valueHelp>
        <valueHelp>
          <format>rspf</format>
          <description>Radio Shortest Path First (officially CPHB)</description>
        </valueHelp>
        <valueHelp>
          <format>vmtp</format>
          <description>Versatile Message Transport</description>
        </valueHelp>
        <valueHelp>
          <format>eigrp</format>
          <description>Enhanced Interior Routing Protocol (Cisco)</description>
        </valueHelp>
        <valueHelp>
          <format>ospf</format>
          <description>Open Shortest Path First IGP</description>
        </valueHelp>
        <valueHelp>
          <format>ax.25</format>
          <description>AX.25 frames</description>
        </valueHelp>
        <valueHelp>
          <format>ipip</format>
          <description>IP-within-IP Encapsulation Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>etherip</format>
          <description>Ethernet-within-IP Encapsulation [RFC3378]</description>
        </valueHelp>
        <valueHelp>
          <format>encap</format>
          <description>Yet Another IP encapsulation [RFC1241]</description>
        </valueHelp>
        <valueHelp>
          <format>99</format>
          <description>Any private encryption scheme</description>
        </valueHelp>
        <valueHelp>
          <format>pim</format>
          <description>Protocol Independent Multicast</description>
        </valueHelp>
        <valueHelp>
          <format>ipcomp</format>
          <description>IP Payload Compression Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>vrrp</format>
          <description>Virtual Router Redundancy Protocol [RFC5798]</description>
        </valueHelp>
        <valueHelp>
          <format>l2tp</format>
          <description>Layer Two Tunneling Protocol [RFC2661]</description>
        </valueHelp>
        <valueHelp>
          <format>isis</format>
          <description>IS-IS over IPv4</description>
        </valueHelp>
        <valueHelp>
          <format>sctp</format>
          <description>Stream Control Transmission Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>fc</format>
          <description>Fibre Channel</description>
        </valueHelp>
        <valueHelp>
          <format>mobility-header</format>
          <description>Mobility Support for IPv6 [RFC3775]</description>
        </valueHelp>
        <valueHelp>
          <format>udplite</format>
          <description>UDP-Lite [RFC3828]</description>
        </valueHelp>
        <valueHelp>
          <format>mpls-in-ip</format>
          <description>MPLS-in-IP [RFC4023]</description>
        </valueHelp>
        <valueHelp>
          <format>manet</format>
          <description>MANET Protocols [RFC5498]</description>
        </valueHelp>
        <valueHelp>
          <format>hip</format>
          <description>Host Identity Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>shim6</format>
          <description>Shim6 Protocol</description>
        </valueHelp>
        <valueHelp>
          <format>wesp</format>
          <description>Wrapped Encapsulating Security Payload</description>
        </valueHelp>
        <valueHelp>
          <format>rohc</format>
          <description>Robust Header Compression</description>
        </valueHelp>
        <valueHelp>
          <format>u32:0-255</format>
          <description>IP protocol number</description>
        </valueHelp>
        <constraint>
          <validator name="ip-protocol"/>
        </constraint>
      </properties>
      <defaultValue>all</defaultValue>
    </leafNode>
    <node name="source">
      <properties>
        <help>NAT source parameters</help>
      </properties>
      <children>
        #include <include/firewall/fqdn.xml.i>
        #include <include/nat-address.xml.i>
        #include <include/nat-port.xml.i>
        #include <include/firewall/source-destination-group.xml.i>
      </children>
    </node>
  </children>
</tagNode>
<!-- include end -->
