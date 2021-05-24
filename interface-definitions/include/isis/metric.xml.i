<!-- include start from isis/metric.xml.i -->
<leafNode name="metric">
  <properties>
    <help>Set default metric for circuit</help>
    <valueHelp>
      <format>u32:0-16777215</format>
      <description>Default metric value</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-16777215"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
