<leafNode name="mode">
  <properties>
    <help>Authentication mode used by this server</help>
    <valueHelp>
      <format>local</format>
      <description>Use local username/password configuration</description>
    </valueHelp>
    <valueHelp>
      <format>radius</format>
      <description>Use RADIUS server for user autentication</description>
    </valueHelp>
    <constraint>
      <regex>(local|radius)</regex>
    </constraint>
    <completionHelp>
      <list>local radius</list>
    </completionHelp>
  </properties>
</leafNode>
