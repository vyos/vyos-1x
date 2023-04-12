<!-- included start from ldp-sync.xml.i -->
<node name="ldp-sync">
  <properties>
    <help>Show LDP-IGP synchronization information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/vtysh-generic-interface-tagNode.xml.i>
  </children>
</node>
<!-- included end -->