<!-- included start from bgp-capability.xml.i -->
<node name="capability">
  <properties>
    <help>Advertise capabilities to this peer-group</help>
  </properties>
  <children>
    #include <include/bgp-capability-dynamic.xml.i>
    <leafNode name="extended-nexthop">
      <properties>
        <help>Advertise extended-nexthop capability to this neighbor</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- included end -->
