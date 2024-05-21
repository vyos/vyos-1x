<!-- include start from qos/class-match-mark.xml.i -->
<leafNode name="mark">
  <properties>
    <help>Match on mark applied by firewall</help>
    <valueHelp>
      <format>u32</format>
      <description>FW mark to match</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967295"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
