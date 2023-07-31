<!-- included start from ospfv3/neighbor.xml.i -->
<node name="neighbor">
  <properties>
    <help>Show OSPFv3 neighbor information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/frr-detail.xml.i>
    <node name="drchoice">
      <properties>
        <help>Show neighbor DR choice information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </node>
  </children>
</node>
<!-- included end -->
