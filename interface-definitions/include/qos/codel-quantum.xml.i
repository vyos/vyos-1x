<!-- include start from qos/codel-quantum.xml.i -->
<leafNode name="codel-quantum">
  <properties>
    <help>Deficit in the fair queuing algorithm</help>
    <valueHelp>
      <format>u32:0-1048576</format>
      <description>Number of bytes used as 'deficit'</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-1048576"/>
    </constraint>
    <constraintErrorMessage>Interval must be in range 0 to 1048576</constraintErrorMessage>
  </properties>
  <defaultValue>1514</defaultValue>
</leafNode>
<!-- include end -->
