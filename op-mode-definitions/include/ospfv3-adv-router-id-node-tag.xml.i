<!-- included start from ospfv3-adv-router-id-node-tag.xml.i -->
<node name="node.tag">
  <properties>
    <help>Search by Advertising Router ID</help>
    <completionHelp>
      <list>&lt;x.x.x.x&gt;</list>
    </completionHelp>
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
