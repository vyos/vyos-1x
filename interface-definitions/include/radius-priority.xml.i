<!-- include start from radius-priority.xml.i -->
<leafNode name="priority">
  <properties>
    <help>Server priority</help>
    <valueHelp>
      <format>u32:1-255</format>
      <description>Server priority</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-255"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
