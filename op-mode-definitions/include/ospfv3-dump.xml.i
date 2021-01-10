<!-- included start from ospfv3-dump.xml.i -->
<node name="dump">
  <properties>
    <help>Show dump of LSAs</help>
  </properties>
  <!-- FRR uses ospf6 where we use ospfv3, thus alter the command -->
  <command>vtysh -c "show ipv6 ospf6 ${@:4}"</command>
</node>
<!-- included end -->
