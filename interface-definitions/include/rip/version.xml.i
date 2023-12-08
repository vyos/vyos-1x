<!-- include start from rip/version.xml.i -->
<leafNode name="version">
  <properties>
    <help>Limit RIP protocol version</help>
    <valueHelp>
      <format>1</format>
      <description>Allow RIPv1 only</description>
    </valueHelp>
    <valueHelp>
      <format>2</format>
      <description>Allow RIPv2 only</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-2"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
