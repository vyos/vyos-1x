<!-- included start from ospfv3/linkstate-id-node-tag.xml.i -->
<node name="node.tag">
  <properties>
    <help>Search by Link state ID</help>
    <completionHelp>
      <list>&lt;x.x.x.x&gt;</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/frr-detail.xml.i>
    #include <include/ospfv3/dump.xml.i>
    #include <include/ospfv3/internal.xml.i>
    #include <include/ospfv3/self-originated.xml.i>
  </children>
</node>
<!-- included end -->
