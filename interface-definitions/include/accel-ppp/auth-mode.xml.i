<!-- include start from accel-ppp/auth-mode.xml.i -->
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
    <valueHelp>
      <format>noauth</format>
      <description>Authentication disabled</description>
    </valueHelp>
    <constraint>
      <regex>(local|radius|noauth)</regex>
    </constraint>
    <completionHelp>
      <list>local radius noauth</list>
    </completionHelp>
  </properties>
  <defaultValue>local</defaultValue>
</leafNode>
<!-- include end -->
