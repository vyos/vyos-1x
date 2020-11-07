<!-- included start from interface-ipv4-options.xml.i -->
<node name="ip">
  <properties>
    <help>IPv4 routing parameters</help>
  </properties>
  <children>
    #include <include/interface-arp-cache-timeout.xml.i>
    #include <include/interface-disable-arp-filter.xml.i>
    #include <include/interface-disable-forwarding.xml.i>
    #include <include/interface-enable-arp-accept.xml.i>
    #include <include/interface-enable-arp-announce.xml.i>
    #include <include/interface-enable-arp-ignore.xml.i>
    #include <include/interface-enable-proxy-arp.xml.i>
    #include <include/interface-proxy-arp-pvlan.xml.i>
  </children>
</node>
<!-- included end -->
