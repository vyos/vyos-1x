<!-- include start from qos/queue-limit-1-4294967295.xml.i -->
<leafNode name="queue-limit">
  <properties>
    <help>Maximum queue size</help>
    <valueHelp>
      <format>u32:1-4294967295</format>
      <description>Queue size in packets</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967295"/>
    </constraint>
    <constraintErrorMessage>Queue limit must be greater than zero</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
