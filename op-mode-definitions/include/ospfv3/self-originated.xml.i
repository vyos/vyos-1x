<!-- included start from ospfv3/self-originated.xml.i -->
<node name="self-originated">
  <properties>
    <help>Show Self-originated LSAs</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/frr-detail.xml.i>
    #include <include/ospfv3/dump.xml.i>
    #include <include/ospfv3/internal.xml.i>
  </children>
</node>
<!-- included end -->
