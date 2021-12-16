<!-- included start from show-route-kernel.xml.i -->
<leafNode name="kernel">
  <properties>
    <help>Kernel routes (not installed via the zebra RIB)</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<!-- included end -->
