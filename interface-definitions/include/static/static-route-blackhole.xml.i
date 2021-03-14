<!-- include start from static/static-route-blackhole.xml.i -->
<node name="blackhole">
  <properties>
    <help>Silently discard packets when matched</help>
  </properties>
  <children>
    #include <include/static/static-route-distance.xml.i>
  </children>
</node>
<!-- include end -->
