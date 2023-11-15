<!-- include start from pim/dr-priority.xml.i -->
<leafNode name="dr-priority">
  <properties>
    <help>Designated router election priority</help>
    <valueHelp>
      <format>u32:1-4294967295</format>
      <description>DR Priority</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967295"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
