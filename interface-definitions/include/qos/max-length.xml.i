<!-- include start from qos/max-length.xml.i -->
<leafNode name="max-length">
  <properties>
    <help>Maximum packet length (ipv4)</help>
    <valueHelp>
      <format>u32:0-65535</format>
      <description>Maximum packet/payload length</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-65535"/>
    </constraint>
    <constraintErrorMessage>Maximum IPv4 total packet length is 65535</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
