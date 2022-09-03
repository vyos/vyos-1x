<!-- include start from firewall/gt.xml.i -->
<leafNode name="gt">
  <properties>
    <help>Match on greater then value</help>
    <valueHelp>
      <format>u32:0-255</format>
      <description>Greater then value</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
