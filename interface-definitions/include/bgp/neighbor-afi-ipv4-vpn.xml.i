<!-- include start from bgp/neighbor-afi-ipv4-vpn.xml.i -->
<node name="ipv4-vpn">
  <properties>
    <help>IPv4 VPN BGP neighbor parameters</help>
  </properties>
  <children>
    #include <include/bgp/afi-ipv4-prefix-list.xml.i>
    #include <include/bgp/neighbor-afi-ipv4-ipv6-common.xml.i>
  </children>
</node>
<!-- include end -->
