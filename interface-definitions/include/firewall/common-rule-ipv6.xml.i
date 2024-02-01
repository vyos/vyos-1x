<!-- include start from firewall/common-rule-ipv6.xml.i -->
#include <include/firewall/common-rule-inet.xml.i>
#include <include/firewall/hop-limit.xml.i>
<node name="add-address-to-group">
  <properties>
    <help>Add ipv6 address to dynamic ipv6-address-group</help>
  </properties>
  <children>
    <node name="source-address">
      <properties>
        <help>Add source ipv6 addresses to dynamic ipv6-address-group</help>
      </properties>
      <children>
        #include <include/firewall/add-dynamic-ipv6-address-groups.xml.i>
      </children>
    </node>
    <node name="destination-address">
      <properties>
        <help>Add destination ipv6 addresses to dynamic ipv6-address-group</help>
      </properties>
      <children>
        #include <include/firewall/add-dynamic-ipv6-address-groups.xml.i>
      </children>
    </node>
  </children>
</node>
<node name="destination">
  <properties>
    <help>Destination parameters</help>
  </properties>
  <children>
    #include <include/firewall/address-ipv6.xml.i>
    #include <include/firewall/address-mask-ipv6.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group-ipv6.xml.i>
    #include <include/firewall/source-destination-dynamic-group-ipv6.xml.i>
  </children>
</node>
<node name="icmpv6">
  <properties>
    <help>ICMPv6 type and code information</help>
  </properties>
  <children>
    <leafNode name="code">
      <properties>
        <help>ICMPv6 code</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMPv6 code (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="type">
      <properties>
        <help>ICMPv6 type</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMPv6 type (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/firewall/icmpv6-type-name.xml.i>
  </children>
</node>
<leafNode name="jump-target">
  <properties>
    <help>Set jump target. Action jump must be defined to use this setting</help>
    <completionHelp>
      <path>firewall ipv6 name</path>
    </completionHelp>
  </properties>
</leafNode>
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address-ipv6.xml.i>
    #include <include/firewall/address-mask-ipv6.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group-ipv6.xml.i>
    #include <include/firewall/source-destination-dynamic-group-ipv6.xml.i>
  </children>
</node>
<!-- include end -->