<!-- include start from firewall/eq.xml.i -->
<leafNode name="eq">
  <properties>
    <help>Match on equal value</help>
    <valueHelp>
      <format>u32:0-255</format>
      <description>Equal to value</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->