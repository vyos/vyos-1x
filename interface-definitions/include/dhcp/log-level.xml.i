<!-- include start from dhcp/log-level.xml.i -->
<leafNode name="log-level">
  <properties>
    <help>Logging level</help>
    <completionHelp>
      <list>fatal error warn info debug</list>
    </completionHelp>
    <valueHelp>
      <format>fatal</format>
      <description>Fatal log level</description>
    </valueHelp>
    <valueHelp>
      <format>error</format>
      <description>Error log level</description>
    </valueHelp>
    <valueHelp>
      <format>warn</format>
      <description>Warning log level</description>
    </valueHelp>
    <valueHelp>
      <format>info</format>
      <description>Informational log level</description>
    </valueHelp>
    <valueHelp>
      <format>debug</format>
      <description>Debug log level</description>
    </valueHelp>
    <constraint>
      <regex>(fatal|error|warn|info|debug)</regex>
    </constraint>
  </properties>
  <defaultValue>info</defaultValue>
</leafNode>
<!-- include end -->