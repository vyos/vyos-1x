<!-- included start from bgp/reset-bgp-afi-common.xml.i -->
<node name="external">
  <properties>
    <help>Reset all external peers</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/bgp/reset-bgp-neighbor-options.xml.i>
  </children>
</node>
<tagNode name="1-4294967295">
  <properties>
    <help>Reset peers with the AS number</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/bgp/reset-bgp-neighbor-options.xml.i>
  </children>
</tagNode>
<!-- included end -->
