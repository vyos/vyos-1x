<!-- include start from policy/tag.xml.i -->
<leafNode name="tag">
  <properties>
    <help>Route tag value</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Route tag</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
