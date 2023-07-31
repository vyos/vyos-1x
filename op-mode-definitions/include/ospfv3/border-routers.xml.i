<!-- included start from ospfv3/border-routers.xml.i -->
<node name="border-routers">
  <properties>
    <help>Show OSPFv3 border-router (ABR and ASBR) information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/frr-detail.xml.i>
  </children>
</node>
<tagNode name="border-routers">
  <properties>
    <help>Border router ID</help>
    <completionHelp>
      <list>&lt;x.x.x.x&gt;</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<!-- included end -->
