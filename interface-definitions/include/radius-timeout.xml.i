<!-- include start from radius-timeout.xml.i -->
<leafNode name="timeout">
  <properties>
    <help>Session timeout</help>
    <valueHelp>
      <format>u32:1-240</format>
      <description>Session timeout in seconds (default: 2)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-240"/>
    </constraint>
    <constraintErrorMessage>Timeout must be between 1 and 240 seconds</constraintErrorMessage>
  </properties>
  <defaultValue>2</defaultValue>
</leafNode>
<!-- include end -->
