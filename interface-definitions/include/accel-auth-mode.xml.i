<!-- included start from accel-auth-mode.xml.i -->
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
  <defaultValue>local</defaultValue>
</leafNode>
<!-- included end -->
