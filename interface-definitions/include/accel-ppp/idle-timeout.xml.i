<!-- include start from accel-ppp/idle-timeout.xml.i -->
<leafNode name="idle-timeout">
  <properties>
    <help>Disconnect idle sessions after the specified time (in seconds)</help>
    <valueHelp>
      <format>u32:0-86400</format>
      <description>Idle timeout in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-86400"/>
    </constraint>
    <constraintErrorMessage>Idle timeout must be in range 0 to 86400</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
