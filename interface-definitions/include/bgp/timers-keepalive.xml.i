<!-- include start from bgp/timers-keepalive.xml.i -->
<leafNode name="keepalive">
  <properties>
    <help>BGP keepalive interval for this neighbor</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Keepalive interval in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
