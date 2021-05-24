<!-- include start from firewall/port.xml.i -->
<leafNode name="port">
  <properties>
    <help>Port</help>
    <valueHelp>
      <format>txt</format>
      <description>Named port (any name in /etc/services, e.g., http)</description>
    </valueHelp>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Numbered port</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;start-end&gt;</format>
      <description>Numbered port range (e.g. 1001-1005)</description>
    </valueHelp>
    <valueHelp>
      <format> </format>
      <description>\n\n  Multiple destination ports can be specified as a comma-separated list.\n  The whole list can also be negated using '!'.\n  For example: '!22,telnet,http,123,1001-1005'</description>
    </valueHelp>
  </properties>
</leafNode>
<!-- include end -->
