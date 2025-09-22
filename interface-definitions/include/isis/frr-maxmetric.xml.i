<!-- include start from isis/frr-maxmetric.xml.i -->
<leafNode name="maximum-metric">
  <properties>
    <help>Limit remote LFA node selection within the metric</help>
    <valueHelp>
      <format>u32:1-16777215</format>
      <description>Metric value</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-16777215"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->