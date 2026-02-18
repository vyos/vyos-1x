<!-- include start from firewall/source-destination-group-ipv6.xml.i -->
<node name="group">
  <properties>
    <help>Group</help>
  </properties>
  <children>
    <leafNode name="address-group">
      <properties>
        <help>Group of addresses</help>
        <completionHelp>
          <path>firewall group ipv6-address-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="network-group">
      <properties>
        <help>Group of networks</help>
        <completionHelp>
          <path>firewall group ipv6-network-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    #include <include/firewall/mac-group.xml.i>
    #include <include/firewall/domain-group.xml.i>
    #include <include/firewall/port-group.xml.i>
  </children>
</node>
<!-- include end -->
