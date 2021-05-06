<!-- include start from bgp/neighbor-afi-l2vpn-evpn.xml.i -->
<node name="l2vpn-evpn">
  <properties>
    <help>L2VPN EVPN BGP settings</help>
  </properties>
  <children>
    #include <include/bgp/afi-allowas-in.xml.i>
    #include <include/bgp/afi-attribute-unchanged.xml.i>
    #include <include/bgp/afi-nexthop-self.xml.i>
    #include <include/bgp/afi-route-map.xml.i>
    #include <include/bgp/afi-route-reflector-client.xml.i>
    #include <include/bgp/afi-route-server-client.xml.i>
    #include <include/bgp/afi-soft-reconfiguration.xml.i>
  </children>
</node>
<!-- include end -->
