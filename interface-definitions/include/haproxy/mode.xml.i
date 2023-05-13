<!-- include start from haproxy/mode.xml.i -->
<leafNode name="mode">
  <properties>
    <help>Proxy mode</help>
    <completionHelp>
      <list>http tcp</list>
    </completionHelp>
    <constraintErrorMessage>invalid value</constraintErrorMessage>
    <valueHelp>
      <format>http</format>
      <description>HTTP proxy mode</description>
    </valueHelp>
    <valueHelp>
      <format>tcp</format>
      <description>TCP proxy mode</description>
    </valueHelp>
    <constraint>
      <regex>(http|tcp)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
