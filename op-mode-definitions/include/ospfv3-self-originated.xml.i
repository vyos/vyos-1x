<!-- included start from ospfv3-self-originated.xml.i -->
<node name="self-originated">
  <properties>
    <help>Show Self-originated LSAs</help>
  </properties>
  <command>vtysh -c "show ipv6 ospf6 database as-external $6 self-originated"</command>
  <children>
    #include <include/ospfv3-detail.xml.i>
    #include <include/ospfv3-dump.xml.i>
    #include <include/ospfv3-internal.xml.i>
  </children>
</node>
<!-- included end -->
