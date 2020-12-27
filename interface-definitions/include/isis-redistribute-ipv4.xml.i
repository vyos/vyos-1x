<!-- included start from isis-redistribute-ipv4.xml.i -->
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
    <leafNode name="route-map">
      <properties>
        <help>Route map reference</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
      </properties>
    </leafNode>
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
    <leafNode name="route-map">
      <properties>
        <help>Route map reference</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- included end -->
