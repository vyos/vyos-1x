<!-- included start from bgp/received-routes.xml.i -->
<node name="received-routes">
  <properties>
    <help>Show received routes from a BGP neighbor</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/vtysh-generic-detail-wide.xml.i>
    #include <include/vtysh-generic-wide.xml.i>
  </children>
</node>
<!-- included end -->
