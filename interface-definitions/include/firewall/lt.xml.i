<!-- include start from firewall/lt.xml.i -->
<leafNode name="lt">
  <properties>
    <help>Match on less then value</help>
    <valueHelp>
      <format>u32:0-255</format>
      <description>Less then value</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
