<!-- include start from firewall/source-destination-group-inet.xml.i -->
<node name="group">
  <properties>
    <help>Group</help>
  </properties>
  <children>
    <leafNode name="ipv4-address-group">
      <properties>
        <help>Group of IPv4 addresses</help>
        <completionHelp>
          <path>firewall group address-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="ipv6-address-group">
      <properties>
        <help>Group of IPv6 addresses</help>
        <completionHelp>
          <path>firewall group ipv6-address-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    #include <include/firewall/mac-group.xml.i>
    <leafNode name="ipv4-network-group">
      <properties>
        <help>Group of IPv4 networks</help>
        <completionHelp>
          <path>firewall group network-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="ipv6-network-group">
      <properties>
        <help>Group of IPv6 networks</help>
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
