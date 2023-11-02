<!-- include start from accel-ppp/max-concurrent-sessions.xml.i -->
<leafNode name="max-concurrent-sessions">
  <properties>
    <help>Maximum number of concurrent session start attempts</help>
    <valueHelp>
      <format>u32:0-65535</format>
      <description>Maximum number of concurrent session start attempts</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--allow-range --range 0-65535"/>
    </constraint>
    <constraintErrorMessage>Maximum concurent sessions must be in range 0-65535</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
