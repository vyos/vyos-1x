<!-- included start from bgp-neighbor-afi-ipv4-unicast.xml.i -->
<node name="ipv4-unicast">
  <properties>
    <help>IPv4 BGP neighbor parameters</help>
  </properties>
  <children>
    <node name="capability">
      <properties>
        <help>Advertise capabilities to this neighbor (IPv4)</help>
      </properties>
      <children>
        #include <include/bgp-afi-capability-orf.xml.i>
        #include <include/bgp-capability-dynamic.xml.i>
      </children>
    </node>
    #include <include/bgp-afi-peer-group.xml.i>
    #include <include/bgp-afi-ipv4-prefix-list.xml.i>
    #include <include/bgp-afi-common.xml.i>
  </children>
</node>
<!-- included end -->
