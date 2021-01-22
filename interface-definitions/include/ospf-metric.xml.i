<!-- included start from ospf-metric.xml.i -->
<leafNode name="metric">
  <properties>
    <help>OSPF default metric</help>
    <valueHelp>
      <format>u32:0-16777214</format>
      <description>Default metric</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-16777214"/>
    </constraint>
  </properties>
</leafNode>
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
<leafNode name="route-map">
  <properties>
    <help>Route map reference</help>
    <completionHelp>
      <path>policy route-map</path>
    </completionHelp>
  </properties>
</leafNode>
<!-- included end -->
