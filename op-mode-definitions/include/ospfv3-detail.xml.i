<!-- included start from ospfv3-detail.xml.i -->
<node name="detail">
  <properties>
    <help>Show detailed information</help>
  </properties>
  <!-- FRR uses ospf6 where we use ospfv3, thus alter the command -->
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<!-- included end -->
