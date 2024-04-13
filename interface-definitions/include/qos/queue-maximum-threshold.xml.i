<!-- include start from qos/queue-maximum-threshold.xml.i -->
<leafNode name="maximum-threshold">
  <properties>
    <help>Maximum threshold for random detection</help>
    <valueHelp>
      <format>u32:0-4096</format>
      <description>Maximum threshold in packets</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4096"/>
    </constraint>
    <constraintErrorMessage>Threshold must be between 0 and 4096</constraintErrorMessage>
  </properties>
  <defaultValue>18</defaultValue>
</leafNode>
<!-- include end -->
