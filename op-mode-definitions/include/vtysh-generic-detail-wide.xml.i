<!-- included start from vtysh-generic-detail-wide.xml.i -->
<node name="detail">
  <properties>
    <help>Detailed information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/vtysh-generic-wide.xml.i>
  </children>
</node>
<!-- included end -->
