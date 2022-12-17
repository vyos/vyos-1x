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
    <leafNode name="domain-group">
      <properties>
        <help>Group of domains</help>
        <completionHelp>
          <path>firewall group domain-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    #include <include/firewall/mac-group.xml.i>
    <leafNode name="network-group">
      <properties>
        <help>Group of networks</help>
        <completionHelp>
          <path>firewall group ipv6-network-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="port-group">
      <properties>
        <help>Group of ports</help>
        <completionHelp>
          <path>firewall group port-group</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
