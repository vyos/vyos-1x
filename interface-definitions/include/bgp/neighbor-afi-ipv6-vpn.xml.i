<!-- include start from bgp/neighbor-afi-ipv6-vpn.xml.i -->
<node name="ipv6-vpn">
  <properties>
    <help>IPv6 VPN BGP neighbor parameters</help>
  </properties>
  <children>
    #include <include/bgp/afi-ipv6-nexthop-local.xml.i>
    #include <include/bgp/afi-ipv6-prefix-list.xml.i>
    #include <include/bgp/neighbor-afi-ipv4-ipv6-common.xml.i>
  </children>
</node>
<!-- include end -->
