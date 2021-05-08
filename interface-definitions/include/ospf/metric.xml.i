<!-- include start from ospf/metric.xml.i -->
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
<!-- include end -->
