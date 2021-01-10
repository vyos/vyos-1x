<!-- included start from monitor-background.xml.i -->
<node name="background">
  <properties>
    <help>Monitor in background</help>
  </properties>
  <children>
    <node name="start">
      <properties>
        <help>Start background monitoring</help>
      </properties>
      <command>${vyatta_bindir}/vyatta-monitor-background ${3^^} ${3}</command>
    </node>
    <node name="stop">
      <properties>
        <help>Stop background monitoring</help>
      </properties>
      <command>${vyatta_bindir}/vyatta-monitor-background-stop ${3^^}</command>
    </node>
  </children>
</node>
<!-- included end -->
