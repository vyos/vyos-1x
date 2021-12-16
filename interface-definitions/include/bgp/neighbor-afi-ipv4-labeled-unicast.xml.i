<!-- include start from bgp/neighbor-afi-ipv4-labeled-unicast.xml.i -->
<node name="ipv4-labeled-unicast">
  <properties>
    <help>IPv4 Labeled Unicast BGP neighbor parameters</help>
  </properties>
  <children>
    <node name="capability">
      <properties>
        <help>Advertise capabilities to this neighbor (IPv4)</help>
      </properties>
      <children>
        #include <include/bgp/afi-capability-orf.xml.i>
      </children>
    </node>
    #include <include/bgp/afi-ipv4-prefix-list.xml.i>
    #include <include/bgp/neighbor-afi-ipv4-ipv6-common.xml.i>
    #include <include/bgp/afi-default-originate.xml.i>
  </children>
</node>
<!-- include end -->
