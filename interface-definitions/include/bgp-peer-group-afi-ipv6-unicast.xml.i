<!-- included start from bgp-peer-group-afi-ipv6-unicast.xml.i -->
<node name="ipv6-unicast">
  <properties>
    <help>IPv6 BGP peer group parameters</help>
  </properties>
  <children>
    <node name="capability">
      <properties>
        <help>Advertise capabilities to this peer-group</help>
      </properties>
      <children>
        #include <include/bgp-afi-capability-orf.xml.i>
        #include <include/bgp-afi-ipv6-capability-dynamic.xml.i>
      </children>
    </node>
    #include <include/bgp-afi-ipv6-nexthop-local.xml.i>
    #include <include/bgp-afi-ipv6-prefix-list.xml.i>
    #include <include/bgp-afi-common.xml.i>
  </children>
</node>
<!-- included end -->
