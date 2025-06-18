<!-- included start from bgp/received.xml.i -->
<node name="received">
  <properties>
    <help>Show information received from BGP neighbor</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <leafNode name="prefix-filter">
      <properties>
        <help>Show prefixlist filter</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
</node>
<!-- included end -->
