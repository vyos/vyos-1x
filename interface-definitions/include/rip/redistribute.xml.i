<!-- include start from rip/redistribute.xml.i -->
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
#include <include/route-map.xml.i>
<!-- include end -->
