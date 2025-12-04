<!-- include start from vpp/acl_port_range.xml.i -->
<leafNode name="port">
  <properties>
    <help>Port number or range</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Numeric IP port</description>
    </valueHelp>
    <valueHelp>
      <format>range</format>
      <description>Numbered port range (e.g., 1001-1005)</description>
    </valueHelp>
    <constraint>
     <validator name="numeric" argument="--allow-range --range 1-65535"/>
    </constraint>
    <constraintErrorMessage>Invalid port or port range</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
