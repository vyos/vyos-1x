<leafNode name="port">
  <properties>
    <help>Port number</help>
    <valueHelp>
      <format>1-65535</format>
      <description>Numeric IP port</description>
    </valueHelp>
    <valueHelp>
      <format>start-end</format>
      <description>Numbered port range (e.g., 1001-1005)</description>
    </valueHelp>
    <valueHelp>
      <format> </format>
      <description>\n\nMultiple destination ports can be specified as a comma-separated list.\nThe whole list can also be negated using '!'.\nFor example: '!22,telnet,http,123,1001-1005'</description>
    </valueHelp>
  </properties>
</leafNode>
