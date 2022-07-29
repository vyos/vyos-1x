<!-- include start from port-port-range.xml.i -->
<leafNode name="port">
  <properties>
    <help>Port number</help>
    <valueHelp>
     <format>txt</format>
     <description>Named port (any name in /etc/services, e.g., http)</description>
    </valueHelp>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Numeric IP port</description>
    </valueHelp>
    <valueHelp>
      <format>start-end</format>
      <description>Numbered port range (e.g. 1001-1005)</description>
    </valueHelp>
    <valueHelp>
      <format/>
      <description>\n\nMultiple destination ports can be specified as a comma-separated list.\nThe whole list can also be negated using '!'.\nFor example: '!22,telnet,http,123,1001-1005'</description>
    </valueHelp>
    <constraint>
     <validator name="port-multi"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
