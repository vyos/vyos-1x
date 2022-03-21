<!-- include start from qos/queue-limit.xml.i -->
<leafNode name="queue-limit">
  <properties>
    <help>Upper limit of the queue</help>
    <valueHelp>
      <format>u32:2-10999</format>
      <description>Queue size in packets</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 2-10999"/>
    </constraint>
    <constraintErrorMessage>Queue limit must greater than 1 and less than 11000</constraintErrorMessage>
  </properties>
  <defaultValue>10240</defaultValue>
</leafNode>
<!-- include end -->
