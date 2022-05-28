<!-- include start from rip/version.xml.i -->
<leafNode name="version">
  <properties>
    <help>RIP protocol version</help>
    <valueHelp>
      <format>1</format>
      <description>RIPv1</description>
    </valueHelp>
    <valueHelp>
      <format>2</format>
      <description>RIPv2</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-2"/>
    </constraint>
  </properties>
  <defaultValue>2</defaultValue>
</leafNode>
<!-- include end -->
