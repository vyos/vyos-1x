<!-- included start from ospfv3/adv-router-id-node-tag.xml.i -->
<node name="node.tag">
  <properties>
    <help>Search by Advertising Router ID</help>
    <completionHelp>
      <list>&lt;x.x.x.x&gt;</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/frr-detail.xml.i>
    #include <include/ospfv3/dump.xml.i>
    #include <include/ospfv3/internal.xml.i>
  </children>
</node>
<!-- included end -->
