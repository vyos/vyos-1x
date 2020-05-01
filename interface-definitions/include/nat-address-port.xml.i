<leafNode name="address">
  <properties>
    <help>IP address, subnet, or range</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address to match</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 prefix to match</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4range</format>
      <description>IPv4 address range to match</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv4</format>
      <description>Match everything except the specified address</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv4net</format>
      <description>Match everything except the specified prefix</description>
    </valueHelp>
    <valueHelp>
      <format>!ipv4range</format>
      <description>Match everything except the specified range</description>
    </valueHelp>
    <!-- TODO: add general iptables constraint script -->
  </properties>
</leafNode>
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
