<!-- include start from bgp/timers-holdtime.xml.i -->
<leafNode name="holdtime">
  <properties>
    <help>Hold timer</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Hold timer in seconds</description>
    </valueHelp>
    <valueHelp>
      <format>0</format>
      <description>Disable hold timer</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-65535"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
