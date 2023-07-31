<!-- included start from ospfv3/interface.xml.i -->
<node name="interface">
  <properties>
    <help>Show OSPFv3 interface information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <node name="prefix">
      <properties>
        <help>Show connected prefixes to advertise</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
      </children>
    </node>
    <tagNode name="prefix">
      <properties>
        <help>Show interface prefix route specific information</help>
        <completionHelp>
          <list>&lt;h:h:h:h:h:h:h:h&gt; &lt;h:h:h:h:h:h:h:h/x&gt;</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
        <node name="match">
          <properties>
            <help>Matched interface prefix information</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </node>
      </children>
    </tagNode>
  </children>
</node>
<tagNode name="interface">
  <properties>
    <help>Specific insterface to examine</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <node name="prefix">
      <properties>
        <help>Show connected prefixes to advertise</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
      </children>
    </node>
    <tagNode name="prefix">
      <properties>
        <help>Show interface prefix route specific information</help>
        <completionHelp>
          <list>&lt;h:h:h:h:h:h:h:h&gt; &lt;h:h:h:h:h:h:h:h/x&gt;</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/frr-detail.xml.i>
        <node name="match">
          <properties>
            <help>Matched interface prefix information</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </node>
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- included end -->
