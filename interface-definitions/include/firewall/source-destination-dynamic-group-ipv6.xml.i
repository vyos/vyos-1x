<!-- include start from firewall/source-destination-dynamic-group-ipv6.xml.i -->
<node name="group">
  <properties>
    <help>Group</help>
  </properties>
  <children>
    <leafNode name="dynamic-address-group">
      <properties>
        <help>Group of dynamic ipv6 addresses</help>
        <completionHelp>
          <path>firewall group dynamic-group ipv6-address-group</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
