<!-- include start from interface/interface-ipv4-options.xml.i -->
<node name="ip">
  <properties>
    <help>IPv4 routing parameters</help>
  </properties>
  <children>
    #include <include/interface/interface-arp-cache-timeout.xml.i>
    #include <include/interface/interface-disable-arp-filter.xml.i>
    #include <include/interface/interface-disable-forwarding.xml.i>
    #include <include/interface/interface-enable-arp-accept.xml.i>
    #include <include/interface/interface-enable-arp-announce.xml.i>
    #include <include/interface/interface-enable-arp-ignore.xml.i>
    #include <include/interface/interface-enable-proxy-arp.xml.i>
    #include <include/interface/interface-proxy-arp-pvlan.xml.i>
    #include <include/interface/interface-source-validation.xml.i>
  </children>
</node>
<!-- include end -->
