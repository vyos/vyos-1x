<!-- include start from qos/flows.xml.i -->
<leafNode name="flows">
  <properties>
    <help>Number of flows into which the incoming packets are classified</help>
    <valueHelp>
      <format>u32:1-65536</format>
      <description>Number of flows</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65536"/>
    </constraint>
    <constraintErrorMessage>Interval must be in range 1 to 65536</constraintErrorMessage>
  </properties>
  <defaultValue>1024</defaultValue>
</leafNode>
<!-- include end -->
