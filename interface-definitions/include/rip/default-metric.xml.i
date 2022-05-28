<!-- include start from rip/default-metric.xml.i -->
<leafNode name="default-metric">
  <properties>
    <help>Metric of redistributed routes</help>
    <valueHelp>
      <format>u32:1-16</format>
      <description>Default metric</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-16"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
