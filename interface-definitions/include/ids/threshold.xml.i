<!-- include start from ids/threshold.xml.i -->
<leafNode name="fps">
  <properties>
    <help>Flows per second</help>
    <valueHelp>
      <format>u32:0-4294967294</format>
      <description>Flows per second</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967294"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="mbps">
  <properties>
    <help>Megabits per second</help>
    <valueHelp>
      <format>u32:0-4294967294</format>
      <description>Megabits per second</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967294"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="pps">
  <properties>
    <help>Packets per second</help>
    <valueHelp>
      <format>u32:0-4294967294</format>
      <description>Packets per second</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967294"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
