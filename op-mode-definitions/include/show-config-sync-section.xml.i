<!-- included start from show-config-sync-section.xml.i -->
<leafNode name="firewall">
  <properties>
    <help>Firewall</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="firewall" --source="$5"</command>
</leafNode>
<node name="interfaces">
  <properties>
    <help>Interfaces</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces" --source="$5"</command>
  <children>
    <leafNode name="bonding">
      <properties>
        <help>Bonding interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces bonding" --source="$5"</command>
    </leafNode>
    <leafNode name="bridge">
      <properties>
        <help>Bridge interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces bridge" --source="$5"</command>
    </leafNode>
    <leafNode name="dummy">
      <properties>
        <help>Dummy interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces dummy" --source="$5"</command>
    </leafNode>
    <leafNode name="ethernet">
      <properties>
        <help>Ethernet interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces ethernet" --source="$5"</command>
    </leafNode>
    <leafNode name="geneve">
      <properties>
        <help>GENEVE interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces geneve" --source="$5"</command>
    </leafNode>
    <leafNode name="input">
      <properties>
        <help>Input interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces input" --source="$5"</command>
    </leafNode>
    <leafNode name="l2tpv3">
      <properties>
        <help>L2TPv3 interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces l2tpv3" --source="$5"</command>
    </leafNode>
    <leafNode name="loopback">
      <properties>
        <help>Loopback interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces loopback" --source="$5"</command>
    </leafNode>
    <leafNode name="macsec">
      <properties>
        <help>MACsec interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces macsec" --source="$5"</command>
    </leafNode>
    <leafNode name="openvpn">
      <properties>
        <help>OpenVPN interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces openvpn" --source="$5"</command>
    </leafNode>
    <leafNode name="pppoe">
      <properties>
        <help>PPPoE interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces pppoe" --source="$5"</command>
    </leafNode>
    <leafNode name="pseudo-ethernet">
      <properties>
        <help>Pseudo-Ethernet interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces pseudo-ethernet" --source="$5"</command>
    </leafNode>
    <leafNode name="sstpc">
      <properties>
        <help>SSTP client interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces sstpc" --source="$5"</command>
    </leafNode>
    <leafNode name="tunnel">
      <properties>
        <help>Tunnel interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces tunnel" --source="$5"</command>
    </leafNode>
    <leafNode name="virtual-ethernet">
      <properties>
        <help>Virtual Ethernet interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces virtual-ethernet" --source="$5"</command>
    </leafNode>
    <leafNode name="vti">
      <properties>
        <help>Virtual tunnel interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces vti" --source="$5"</command>
    </leafNode>
    <leafNode name="vxlan">
      <properties>
        <help>VXLAN interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces vxlan" --source="$5"</command>
    </leafNode>
    <leafNode name="wireguard">
      <properties>
        <help>Wireguard interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces wireguard" --source="$5"</command>
    </leafNode>
    <leafNode name="wireless">
      <properties>
        <help>Wireless interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces wireless" --source="$5"</command>
    </leafNode>
    <leafNode name="wwan">
      <properties>
        <help>WWAN interface</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="interfaces wwan" --source="$5"</command>
    </leafNode>
  </children>
</node>
<leafNode name="nat">
  <properties>
    <help>NAT</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="nat" --source="$5"</command>
</leafNode>
<leafNode name="nat66">
  <properties>
    <help>NAT66</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="nat66" --source="$5"</command>
</leafNode>
<leafNode name="pki">
  <properties>
    <help>Public key infrastructure (PKI)</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="pki" --source="$5"</command>
</leafNode>
<leafNode name="policy">
  <properties>
    <help>Routing policy</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="policy" --source="$5"</command>
</leafNode>
<node name="protocols">
  <properties>
    <help>Routing protocols</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols" --source="$5"</command>
  <children>
    <leafNode name="babel">
      <properties>
        <help>Babel Routing Protocol</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols babel" --source="$5"</command>
    </leafNode>
    <leafNode name="bfd">
      <properties>
        <help>Bidirectional Forwarding Detection (BFD)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols bfd" --source="$5"</command>
    </leafNode>
    <leafNode name="bgp">
      <properties>
        <help>Border Gateway Protocol (BGP)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols bgp" --source="$5"</command>
    </leafNode>
    <leafNode name="failover">
      <properties>
        <help>Failover route</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols failover" --source="$5"</command>
    </leafNode>
    <leafNode name="igmp-proxy">
      <properties>
        <help>Internet Group Management Protocol (IGMP) proxy</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols igmp-proxy" --source="$5"</command>
    </leafNode>
    <leafNode name="isis">
      <properties>
        <help>Intermediate System to Intermediate System (IS-IS)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols isis" --source="$5"</command>
    </leafNode>
    <leafNode name="mpls">
      <properties>
        <help>Multiprotocol Label Switching (MPLS)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols mpls" --source="$5"</command>
    </leafNode>
    <leafNode name="nhrp">
      <properties>
        <help>Next Hop Resolution Protocol (NHRP) parameters</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols nhrp" --source="$5"</command>
    </leafNode>
    <leafNode name="ospf">
      <properties>
        <help>Open Shortest Path First (OSPF)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols ospf" --source="$5"</command>
    </leafNode>
    <leafNode name="ospfv3">
      <properties>
        <help>Open Shortest Path First (OSPF) for IPv6</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols ospfv3" --source="$5"</command>
    </leafNode>
    <leafNode name="pim">
      <properties>
        <help>Protocol Independent Multicast (PIM) and IGMP</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols pim" --source="$5"</command>
    </leafNode>
    <leafNode name="pim6">
      <properties>
        <help>Protocol Independent Multicast for IPv6 (PIMv6) and MLD</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols pim6" --source="$5"</command>
    </leafNode>
    <leafNode name="rip">
      <properties>
        <help>Routing Information Protocol (RIP) parameters</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols rip" --source="$5"</command>
    </leafNode>
    <leafNode name="ripng">
      <properties>
        <help>Routing Information Protocol (RIPng) parameters</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols ripng" --source="$5"</command>
    </leafNode>
    <leafNode name="rpki">
      <properties>
        <help>Resource Public Key Infrastructure (RPKI)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols rpki" --source="$5"</command>
    </leafNode>
    <leafNode name="segment-routing">
      <properties>
        <help>Segment-Routing (SR) parameters</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols segment-routing" --source="$5"</command>
    </leafNode>
    <leafNode name="static">
      <properties>
        <help>Static Routing</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="protocols static" --source="$5"</command>
    </leafNode>
  </children>
</node>
<node name="qos">
  <properties>
    <help>Quality of Service (QoS)</help>
  </properties>
  <children>
    <leafNode name="interface">
      <properties>
        <help>Interface to apply QoS policy</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="qos interface" --source="$5"</command>
    </leafNode>
    <leafNode name="policy">
      <properties>
        <help>Service Policy definitions</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="qos policy" --source="$5"</command>
    </leafNode>
  </children>
</node>
<node name="service">
  <properties>
    <help>System services</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service" --source="$5"</command>
  <children>
    <leafNode name="console-server">
      <properties>
        <help>Serial Console Server</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service console-server" --source="$5"</command>
    </leafNode>
    <leafNode name="dhcp-relay">
      <properties>
        <help>Host Configuration Protocol (DHCP) relay agent</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service dhcp-relay" --source="$5"</command>
    </leafNode>
    <leafNode name="dhcp-server">
      <properties>
        <help>Dynamic Host Configuration Protocol (DHCP) for DHCP server</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service dhcp-server" --source="$5"</command>
    </leafNode>
    <leafNode name="dhcpv6-relay">
      <properties>
        <help>DHCPv6 Relay Agent parameters</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service dhcpv6-relay" --source="$5"</command>
    </leafNode>
    <leafNode name="dhcpv6-server">
      <properties>
        <help>DHCP for IPv6 (DHCPv6) server</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service dhcpv6-server" --source="$5"</command>
    </leafNode>
    <leafNode name="dns">
      <properties>
        <help>Domain Name System (DNS) related services</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service dns" --source="$5"</command>
    </leafNode>
    <leafNode name="lldp">
      <properties>
        <help>LLDP settings</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service lldp" --source="$5"</command>
    </leafNode>
    <leafNode name="mdns">
      <properties>
        <help>Multicast DNS (mDNS) parameters</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service mdns" --source="$5"</command>
    </leafNode>
    <leafNode name="monitoring">
      <properties>
        <help>Monitoring services</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service monitoring" --source="$5"</command>
    </leafNode>
    <leafNode name="ndp-proxy">
      <properties>
        <help>Neighbor Discovery Protocol (NDP) Proxy</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service ndp-proxy" --source="$5"</command>
    </leafNode>
    <leafNode name="ntp">
      <properties>
        <help>Network Time Protocol (NTP) configuration</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service ntp" --source="$5"</command>
    </leafNode>
    <leafNode name="snmp">
      <properties>
        <help>Simple Network Management Protocol (SNMP)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service snmp" --source="$5"</command>
    </leafNode>
    <leafNode name="tftp-server">
      <properties>
        <help>Trivial File Transfer Protocol (TFTP) server</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service tftp-server" --source="$5"</command>
    </leafNode>
    <leafNode name="webproxy">
      <properties>
        <help>Webproxy service settings</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="service webproxy" --source="$5"</command>
    </leafNode>
  </children>
</node>
<node name="system">
  <properties>
    <help>System parameters</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system" --source="$5"</command>
  <children>
    <leafNode name="conntrack">
      <properties>
        <help>Connection Tracking</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system conntrack" --source="$5"</command>
    </leafNode>
    <leafNode name="flow-accounting">
      <properties>
        <help>Flow accounting</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system flow-accounting" --source="$5"</command>
    </leafNode>
    <leafNode name="login">
      <properties>
        <help>System User Login</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system login" --source="$5"</command>
    </leafNode>
    <leafNode name="option">
      <properties>
        <help>System Options</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system option" --source="$5"</command>
    </leafNode>
    <leafNode name="sflow">
      <properties>
        <help>sFlow</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system sflow" --source="$5"</command>
    </leafNode>
    <leafNode name="static-host-mapping">
      <properties>
        <help>Map host names to addresses</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system static-host-mapping" --source="$5"</command>
    </leafNode>
    <leafNode name="sysctl">
      <properties>
        <help>Configure kernel parameters at runtime</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system sysctl" --source="$5"</command>
    </leafNode>
    <leafNode name="time-zone">
      <properties>
        <help>Local time zone</help>
      </properties>
      <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="system time-zone" --source="$5"</command>
    </leafNode>
  </children>
</node>
<leafNode name="vpn">
  <properties>
    <help>Virtual Private Network (VPN)</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="vpn" --source="$5"</command>
</leafNode>
<leafNode name="vrf">
  <properties>
    <help>Virtual Routing and Forwarding</help>
  </properties>
  <command>${vyos_op_scripts_dir}/config_sync.py show_sync_diff --section="vrf" --source="$5"</command>
</leafNode>
<!-- included end -->