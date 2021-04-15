<!-- included start from bgp/prefix-bestpath-multipath.xml.i -->
<leafNode name="bestpath">
  <properties>
    <help>Display only the bestpath</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<leafNode name="multipath">
  <properties>
    <help>Display only multipaths</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<leafNode name="longer-prefixes">
  <properties>
    <help>Display route and more specific routes</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<!-- included end -->
