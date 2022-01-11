<!-- include start from ospf/intervals.xml.i -->
<node name="default-information">
  <properties>
    <help>Default route advertisment settings</help>
  </properties>
  <children>
    <node name="originate">
      <properties>
        <help>Distribute a default route</help>
      </properties>
      <children>
        <leafNode name="always">
          <properties>
            <help>Always advertise a default route</help>
            <valueless/>
          </properties>
        </leafNode>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
