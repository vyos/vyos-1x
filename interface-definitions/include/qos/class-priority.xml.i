<!-- include start from qos/class-priority.xml.i -->
<leafNode name="priority">
  <properties>
    <help>Priority for rule evaluation</help>
    <valueHelp>
      <format>u32:0-20</format>
      <description>Priority for match rule evaluation</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-20"/>
    </constraint>
    <constraintErrorMessage>Priority must be between 0 and 20</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
