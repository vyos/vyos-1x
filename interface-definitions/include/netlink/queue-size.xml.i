<!-- include start from netlink/queue-size.xml.i -->
<leafNode name="queue-size">
  <properties>
    <help>Internal message queue size</help>
    <valueHelp>
      <format>u32:100-2147483647</format>
      <description>Queue size</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-2147483647"/>
    </constraint>
    <constraintErrorMessage>Queue size must be between 100 and 2147483647</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
