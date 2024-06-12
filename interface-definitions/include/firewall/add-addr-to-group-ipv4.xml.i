<!-- include start from firewall/add-addr-to-group-ipv4.xml.i -->
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
<!-- include end -->