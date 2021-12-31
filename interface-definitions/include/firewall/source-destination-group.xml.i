<!-- include start from firewall/source-destination-group.xml.i -->
<node name="group">
  <properties>
    <help>Group</help>
  </properties>
  <children>
    <leafNode name="address-group">
      <properties>
        <help>Group of addresses</help>
        <completionHelp>
          <path>firewall group address-group</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="network-group">
      <properties>
        <help>Group of networks</help>
        <completionHelp>
          <path>firewall group network-group</path>
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
