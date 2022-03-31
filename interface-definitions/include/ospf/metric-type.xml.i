<!-- include start from ospf/metric-type.xml.i -->
<leafNode name="metric-type">
  <properties>
    <help>OSPF metric type for default routes</help>
    <valueHelp>
      <format>u32:1-2</format>
      <description>Set OSPF External Type 1/2 metrics</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-2"/>
    </constraint>
  </properties>
  <defaultValue>2</defaultValue>
</leafNode>
<!-- include end -->
