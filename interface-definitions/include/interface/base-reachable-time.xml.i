<!-- include start from interface/base-reachable-time.xml.i -->
<leafNode name="base-reachable-time">
  <properties>
    <help>Base reachable time in seconds</help>
    <valueHelp>
      <format>u32:1-86400</format>
      <description>Base reachable time in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-86400"/>
    </constraint>
    <constraintErrorMessage>Base reachable time must be between 1 and 86400 seconds</constraintErrorMessage>
  </properties>
  <defaultValue>30</defaultValue>
</leafNode>
<!-- include end -->
