<!-- include start from bgp/neighbor-graceful-restart.xml.i -->
<leafNode name="graceful-restart">
  <properties>
    <help>BGP graceful restart functionality</help>
    <completionHelp>
      <list>enable disable restart-helper</list>
    </completionHelp>
    <valueHelp>
      <format>enable</format>
      <description>Enable BGP graceful restart at peer level</description>
    </valueHelp>
    <valueHelp>
      <format>disable</format>
      <description>Disable BGP graceful restart at peer level</description>
    </valueHelp>
    <valueHelp>
      <format>restart-helper</format>
      <description>Enable BGP graceful restart helper only functionality</description>
    </valueHelp>
    <constraint>
      <regex>(enable|disable|restart-helper)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
