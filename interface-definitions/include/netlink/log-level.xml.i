<!-- include start from netlink/log-level.xml.i -->
<leafNode name="log-level">
  <properties>
    <help>Set log-level</help>
    <completionHelp>
      <list>info debug</list>
    </completionHelp>
    <valueHelp>
      <format>info</format>
      <description>Info log level</description>
    </valueHelp>
    <valueHelp>
      <format>debug</format>
      <description>Debug log level</description>
    </valueHelp>
    <constraint>
      <regex>(info|debug)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
