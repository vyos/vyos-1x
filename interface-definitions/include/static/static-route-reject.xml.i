<!-- include start from static/static-route-blackhole.xml.i -->
<node name="reject">
  <properties>
    <help>Emit an ICMP unreachable when matched</help>
  </properties>
  <children>
    #include <include/static/static-route-distance.xml.i>
    #include <include/static/static-route-tag.xml.i>
  </children>
</node>
<!-- include end -->
