<!-- include start from ospf/metric-type.xml.i -->
<leafNode name="metric-type">
  <properties>
    <help>OSPF metric type for default routes (default: 2)</help>
    <valueHelp>
      <format>u32:1-2</format>
      <description>Metric type for default routes</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-2"/>
    </constraint>
  </properties>
  <defaultValue>2</defaultValue>
</leafNode>
<!-- include end -->
