<!-- include start from qos/target.xml.i -->
<leafNode name="target">
  <properties>
    <help>Acceptable minimum standing/persistent queue delay</help>
    <valueHelp>
      <format>u32</format>
      <description>Queue delay in milliseconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967295"/>
    </constraint>
    <constraintErrorMessage>Delay must be in range 0 to 4294967295</constraintErrorMessage>
  </properties>
  <defaultValue>5</defaultValue>
</leafNode>
<!-- include end -->
