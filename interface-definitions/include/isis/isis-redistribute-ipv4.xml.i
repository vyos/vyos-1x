<!-- include start from isis/isis-redistribute-ipv4.xml.i -->
<node name="level-1">
  <properties>
    <help>Redistribute into level-1</help>
  </properties>
  <children>
    <leafNode name="metric">
      <properties>
        <help>Metric for redistributed routes</help>
        <valueHelp>
          <format>u32:0-16777215</format>
          <description>ISIS default metric</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-16777215"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/route-map.xml.i>
  </children>
</node>
<node name="level-2">
  <properties>
    <help>Redistribute into level-2</help>
  </properties>
  <children>
    <leafNode name="metric">
      <properties>
        <help>Metric for redistributed routes</help>
        <valueHelp>
          <format>u32:0-16777215</format>
          <description>ISIS default metric</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-16777215"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/route-map.xml.i>
  </children>
</node>
<!-- include end -->
