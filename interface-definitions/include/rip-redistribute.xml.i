<!-- included start from rip-redistribute.xml.i -->
<leafNode name="metric">
  <properties>
    <help>Metric for redistributed routes</help>
    <valueHelp>
      <format>u32:1-16</format>
      <description>Redistribute route metric</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-16"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="route-map">
  <properties>
    <help>Route map reference</help>
    <valueHelp>
      <format>txt</format>
      <description>Route map reference</description>
    </valueHelp>
    <completionHelp>
      <path>policy route-map</path>
    </completionHelp>
  </properties>
</leafNode>
<!-- included end -->
