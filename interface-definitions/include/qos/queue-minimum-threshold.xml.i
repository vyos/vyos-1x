<!-- include start from qos/queue-minimum-threshold.xml.i -->
<leafNode name="minimum-threshold">
  <properties>
    <help>Minimum threshold for random detection</help>
    <valueHelp>
      <format>u32:0-4096</format>
      <description>Minimum threshold in packets</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4096"/>
    </constraint>
    <constraintErrorMessage>Threshold must be between 0 and 4096</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
