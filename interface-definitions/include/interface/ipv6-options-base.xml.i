<!-- include start from interface/ipv6-options.xml.i -->
<node name="ipv6">
  <properties>
    <help>IPv6 routing parameters</help>
  </properties>
  <children>
    #include <include/interface/adjust-mss.xml.i>
    #include <include/interface/base-reachable-time.xml.i>
    #include <include/interface/disable-forwarding.xml.i>
    #include <include/interface/ipv6-accept-dad.xml.i>
    #include <include/interface/ipv6-dup-addr-detect-transmits.xml.i>
    #include <include/interface/source-validation.xml.i>
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
  </children>
</node>
<!-- include end -->
