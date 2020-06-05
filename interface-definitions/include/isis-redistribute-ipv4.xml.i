<node name="level-1">
  <properties>
    <help>Redistribute into level-1</help>
  </properties>
  <children>
    <leafNode name="metric">
      <properties>
        <help>Metric for redistributed routes</help>
        <valueHelp>
          <format>&lt;0-16777215&gt;</format>
          <description>ISIS default metric</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-16777215"/>
        </constraint>
      </properties>
    </leafNode>
    <tagNode name="route-map">
      <properties>
        <help>Route map reference</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
      </properties>
      <children>
        <leafNode name="metric">
          <properties>
            <help>Metric for redistributed routes</help>
            <valueHelp>
              <format>&lt;0-16777215&gt;</format>
              <description>ISIS default metric</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-16777215"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </tagNode>
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
          <format>&lt;0-16777215&gt;</format>
          <description>ISIS default metric</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-16777215"/>
        </constraint>
      </properties>
    </leafNode>
    <tagNode name="route-map">
      <properties>
        <help>Route map reference</help>
        <completionHelp>
          <path>policy route-map</path>
        </completionHelp>
      </properties>
      <children>
        <leafNode name="metric">
          <properties>
            <help>Metric for redistributed routes</help>
            <valueHelp>
              <format>&lt;0-16777215&gt;</format>
              <description>ISIS default metric</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-16777215"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </tagNode>
  </children>
</node>
