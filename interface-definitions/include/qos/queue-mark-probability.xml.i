<!-- include start from qos/queue-mark-probability.xml.i -->
<leafNode name="mark-probability">
  <properties>
    <help>Mark probability for random detection</help>
    <valueHelp>
      <format>u32</format>
      <description>Numeric value (1/N)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--positive"/>
    </constraint>
    <constraintErrorMessage>Mark probability must be greater than 0</constraintErrorMessage>
  </properties>
  <defaultValue>10</defaultValue>
</leafNode>
<!-- include end -->
