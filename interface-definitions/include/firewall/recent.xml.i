<!-- include start from firewall/recent.xml.i -->
<node name="recent">
  <properties>
    <help>Parameters for matching recently seen sources</help>
  </properties>
  <children>
    <leafNode name="count">
      <properties>
        <help>Source addresses seen more than N times</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Source addresses seen more than N times</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="time">
      <properties>
        <help>Source addresses seen in the last second/minute/hour</help>
        <completionHelp>
          <list>second minute hour</list>
        </completionHelp>
        <valueHelp>
          <format>second</format>
          <description>Source addresses seen COUNT times in the last second</description>
        </valueHelp>
        <valueHelp>
          <format>minute</format>
          <description>Source addresses seen COUNT times in the last minute</description>
        </valueHelp>
        <valueHelp>
          <format>hour</format>
          <description>Source addresses seen COUNT times in the last hour</description>
        </valueHelp>
        <constraint>
          <regex>(second|minute|hour)</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->