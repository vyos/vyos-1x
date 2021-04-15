<!-- included start from bgp-neighbor-afi-ipv4-multicast.xml.i -->
<node name="ipv4-multicast">
  <properties>
    <help>IPv4 Multicast BGP neighbor parameters</help>
  </properties>
  <children>
    <node name="capability">
      <properties>
        <help>Advertise capabilities to this neighbor (IPv4)</help>
      </properties>
      <children>
        #include <include/bgp/bgp-afi-capability-orf.xml.i>
      </children>
    </node>
    #include <include/bgp/bgp-afi-ipv4-prefix-list.xml.i>
    #include <include/bgp/bgp-afi-common.xml.i>
  </children>
</node>
<!-- include end -->
