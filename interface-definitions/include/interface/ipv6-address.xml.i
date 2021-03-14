<!-- include start from interface/ipv6-address.xml.i -->
<node name="address">
  <properties>
    <help>IPv6 address configuration modes</help>
  </properties>
  <children>
    #include <include/interface/ipv6-address-autoconf.xml.i>
    #include <include/interface/ipv6-address-eui64.xml.i>
    #include <include/interface/ipv6-address-no-default-link-local.xml.i>
  </children>
</node>
<!-- include end -->
