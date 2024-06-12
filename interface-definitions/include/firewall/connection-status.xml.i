<!-- include start from firewall/connection-status.xml.i -->
<node name="connection-status">
  <properties>
    <help>Connection status</help>
  </properties>
  <children>
    <leafNode name="nat">
      <properties>
        <help>NAT connection status</help>
        <completionHelp>
          <list>destination source</list>
        </completionHelp>
        <valueHelp>
          <format>destination</format>
          <description>Match connections that are subject to destination NAT</description>
        </valueHelp>
        <valueHelp>
          <format>source</format>
          <description>Match connections that are subject to source NAT</description>
        </valueHelp>
        <constraint>
          <regex>(destination|source)</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->