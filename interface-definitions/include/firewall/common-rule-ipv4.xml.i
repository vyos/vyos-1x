<!-- include start from firewall/common-rule-ipv4.xml.i -->
#include <include/firewall/common-rule-inet.xml.i>
#include <include/firewall/ttl.xml.i>
<node name="add-address-to-group">
  <properties>
    <help>Add ip address to dynamic address-group</help>
  </properties>
  <children>
    <node name="source-address">
      <properties>
        <help>Add source ip addresses to dynamic address-group</help>
      </properties>
      <children>
        #include <include/firewall/add-dynamic-address-groups.xml.i>
      </children>
    </node>
    <node name="destination-address">
      <properties>
        <help>Add destination ip addresses to dynamic address-group</help>
      </properties>
      <children>
        #include <include/firewall/add-dynamic-address-groups.xml.i>
      </children>
    </node>
  </children>
</node>
<node name="destination">
  <properties>
    <help>Destination parameters</help>
  </properties>
  <children>
    #include <include/firewall/address.xml.i>
    #include <include/firewall/address-mask.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
    #include <include/firewall/source-destination-dynamic-group.xml.i>
  </children>
</node>
<node name="icmp">
  <properties>
    <help>ICMP type and code information</help>
  </properties>
  <children>
    <leafNode name="code">
      <properties>
        <help>ICMP code</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMP code (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="type">
      <properties>
        <help>ICMP type</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMP type (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/firewall/icmp-type-name.xml.i>
  </children>
</node>
<leafNode name="jump-target">
  <properties>
    <help>Set jump target. Action jump must be defined to use this setting</help>
    <completionHelp>
      <path>firewall ipv4 name</path>
    </completionHelp>
  </properties>
</leafNode>
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address.xml.i>
    #include <include/firewall/address-mask.xml.i>
    #include <include/firewall/fqdn.xml.i>
    #include <include/firewall/geoip.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
    #include <include/firewall/source-destination-dynamic-group.xml.i>
  </children>
</node>
<!-- include end -->