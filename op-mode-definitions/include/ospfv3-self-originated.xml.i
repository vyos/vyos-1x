<!-- included start from ospfv3-self-originated.xml.i -->
<node name="self-originated">
  <properties>
    <help>Show Self-originated LSAs</help>
  </properties>
  <!-- FRR uses ospf6 where we use ospfv3, thus alter the command -->
  <command>vtysh -c "show ipv6 ospf6 ${@:4}"</command>
  <children>
    #include <include/ospfv3-detail.xml.i>
    #include <include/ospfv3-dump.xml.i>
    #include <include/ospfv3-internal.xml.i>
  </children>
</node>
<!-- included end -->
