<!-- include start from port-number-start-zero.xml.i -->
<leafNode name="port">
  <properties>
    <help>Port number used by connection</help>
    <valueHelp>
      <format>u32:0-65535</format>
      <description>Numeric IP port</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-65535"/>
    </constraint>
    <constraintErrorMessage>Port number must be in range 0 to 65535</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
