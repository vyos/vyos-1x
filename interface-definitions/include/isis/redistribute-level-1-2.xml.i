<!-- include start from isis/redistribute-level-1-2.xml.i -->
<node name="level-1">
  <properties>
    <help>Redistribute into level-1</help>
  </properties>
  <children>
    #include <include/isis/metric.xml.i>
    #include <include/route-map.xml.i>
  </children>
</node>
<node name="level-2">
  <properties>
    <help>Redistribute into level-2</help>
  </properties>
  <children>
    #include <include/isis/metric.xml.i>
    #include <include/route-map.xml.i>
  </children>
</node>
<!-- include end -->
