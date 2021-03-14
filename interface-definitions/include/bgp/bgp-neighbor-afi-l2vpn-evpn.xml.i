<!-- include start from bgp-neighbor-afi-l2vpn-evpn.xml.i -->
<node name="l2vpn-evpn">
  <properties>
    <help>L2VPN EVPN BGP settings</help>
  </properties>
  <children>
    #include <include/bgp/bgp-afi-allowas-in.xml.i>
    #include <include/bgp/bgp-afi-attribute-unchanged.xml.i>
    #include <include/bgp/bgp-afi-nexthop-self.xml.i>
    #include <include/bgp/bgp-afi-route-map.xml.i>
    #include <include/bgp/bgp-afi-route-reflector-client.xml.i>
    #include <include/bgp/bgp-afi-route-server-client.xml.i>
    #include <include/bgp/bgp-afi-soft-reconfiguration.xml.i>
  </children>
</node>
<!-- include end -->
