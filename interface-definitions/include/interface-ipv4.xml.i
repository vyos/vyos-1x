<!-- included start from interface-ipv4.xml.i -->
<node name="ip">
  <properties>
    <help>IPv4 routing parameters</help>
  </properties>
  <children>
    #include <include/interface-disable-arp-filter.xml.i>
    #include <include/interface-enable-arp-accept.xml.i>
    #include <include/interface-enable-arp-announce.xml.i>
    #include <include/interface-enable-arp-ignore.xml.i>
  </children>
</node>
<!-- included end -->
