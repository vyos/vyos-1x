<!-- included start from bgp/advertised-routes.xml.i -->
<node name="advertised-routes">
  <properties>
    <help>Show routes advertised to a BGP neighbor</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/vtysh-generic-detail-wide.xml.i>
    #include <include/vtysh-generic-wide.xml.i>
  </children>
</node>
<!-- included end -->
