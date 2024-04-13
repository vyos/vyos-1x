<!-- include start from qos/queue-average-packet.xml.i -->
<leafNode name="average-packet">
  <properties>
    <help>Average packet size (bytes)</help>
    <valueHelp>
      <format>u32:16-10240</format>
      <description>Average packet size in bytes</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 16-10240"/>
    </constraint>
    <constraintErrorMessage>Average packet size must be between 16 and 10240</constraintErrorMessage>
  </properties>
  <defaultValue>1024</defaultValue>
</leafNode>
<!-- include end -->
