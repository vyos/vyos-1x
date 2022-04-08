<!-- include start from qos/interval.xml.i -->
<leafNode name="interval">
  <properties>
    <help>Interval used to measure the delay</help>
    <valueHelp>
      <format>u32</format>
      <description>Interval in milliseconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967295"/>
    </constraint>
    <constraintErrorMessage>Interval must be in range 0 to 4294967295</constraintErrorMessage>
  </properties>
  <defaultValue>100</defaultValue>
</leafNode>
<!-- include end -->
