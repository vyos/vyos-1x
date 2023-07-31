<!-- included start from ospfv3/route.xml.i -->
<node name="route">
  <properties>
    <help>Show OSPFv3 routing table information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <node name="external-1">
      <properties>
        <help>Show Type-1 External route information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
      </children>
    </node>
    <node name="external-2">
      <properties>
        <help>Show Type-2 External route information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
      </children>
    </node>
    <node name="inter-area">
      <properties>
        <help>Show Inter-Area route information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
      </children>
    </node>
    <node name="intra-area">
      <properties>
        <help>Show Intra-Area route information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
      </children>
    </node>
    #include <include/frr-detail.xml.i>
    <node name="summary">
      <properties>
        <help>Show route table summary</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </node>
  </children>
</node>
<tagNode name="route">
  <properties>
    <help>Show specified route/prefix information</help>
    <completionHelp>
      <list>&lt;h:h:h:h:h:h:h:h&gt; &lt;h:h:h:h:h:h:h:h/x&gt;</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <node name="longer">
      <properties>
        <help>Show routes longer than specified prefix</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </node>
    <node name="match">
      <properties>
        <help>Show routes matching specified prefix</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
      </children>
    </node>
  </children>
</tagNode>
<!-- included end -->
