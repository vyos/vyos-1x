<!-- include start from bgp/neighbor-afi-ipv6-labeled-unicast.xml.i -->
<node name="ipv6-labeled-unicast">
  <properties>
    <help>IPv6 Labeled Unicast BGP neighbor parameters</help>
  </properties>
  <children>
    <node name="capability">
      <properties>
        <help>Advertise capabilities to this neighbor (IPv6)</help>
      </properties>
      <children>
        #include <include/bgp/afi-capability-orf.xml.i>
      </children>
    </node>
    #include <include/bgp/afi-ipv6-nexthop-local.xml.i>
    #include <include/bgp/afi-ipv6-prefix-list.xml.i>
    #include <include/bgp/neighbor-afi-ipv4-ipv6-common.xml.i>
    #include <include/bgp/afi-default-originate.xml.i>
  </children>
</node>
<!-- include end -->
