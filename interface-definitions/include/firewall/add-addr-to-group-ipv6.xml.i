<!-- include start from firewall/add-addr-to-group-ipv6.xml.i -->
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
<!-- include end -->