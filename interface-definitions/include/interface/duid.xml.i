<!-- include start from interface/duid.xml.i -->
<leafNode name="duid">
  <properties>
    <help>DHCP unique identifier (DUID) to be sent by client</help>
    <valueHelp>
      <format>duid</format>
      <description>DHCP unique identifier</description>
    </valueHelp>
    <constraint>
      <regex>([0-9A-Fa-f]{2}:){0,127}([0-9A-Fa-f]{2})</regex>
    </constraint>
    <constraintErrorMessage>Invalid DUID, must be in the format h[[:h]...]</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
