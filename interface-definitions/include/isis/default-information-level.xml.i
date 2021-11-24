<!-- include start from isis/default-information-level.xml.i -->
<node name="level-1">
  <properties>
    <help>Distribute default route into level-1</help>
  </properties>
  <children>
    <leafNode name="always">
      <properties>
        <help>Always advertise default route</help>
        <valueless/>
      </properties>
    </leafNode>
    #include <include/isis/metric.xml.i>
    #include <include/route-map.xml.i>
  </children>
</node>
<node name="level-2">
  <properties>
    <help>Distribute default route into level-2</help>
  </properties>
  <children>
    <leafNode name="always">
      <properties>
        <help>Always advertise default route</help>
        <valueless/>
      </properties>
    </leafNode>
    #include <include/isis/metric.xml.i>
    #include <include/route-map.xml.i>
  </children>
</node>
<!-- include end -->
