<!-- include start from ospf/distance-global.xml.i -->
<leafNode name="global">
  <properties>
    <help>Administrative distance</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Administrative distance</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
