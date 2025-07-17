<!-- included start from isis-common.xml.i -->
<node name="database">
  <properties>
    <help>Show IS-IS link state database</help>
  </properties>
  <children>
    <virtualTagNode>
      <properties>
        <help>Show IS-IS link state database PDU</help>
        <completionHelp>
          <list>lsp-id detail</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </virtualTagNode>
    #include <include/vtysh-generic-detail.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<node name="fast-reroute">
  <properties>
    <help>Show IS-IS fast reroute/loop free alternate (lfa) information</help>
  </properties>
  <children>
    <node name="summary">
      <properties>
        <help>Show summary of fast reroute/loop free alternate (lfa) information</help>
      </properties>
      <children>
        <leafNode name="level-1">
          <properties>
            <help>Show level-1 specific fast reroute/loop free alternate (lfa) information</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </leafNode>
        <leafNode name="level-2">
          <properties>
            <help>Show level-2 specific fast reroute/loop free alternate (lfa) information</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </leafNode>
      </children>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </node>
  </children>
</node>
<leafNode name="hostname">
  <properties>
    <help>Show IS-IS dynamic hostname mapping</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<node name="interface">
  <properties>
    <help>Show IS-IS interfaces</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
  </properties>
  <children>
    #include <include/vtysh-generic-detail.xml.i>
    #include <include/vtysh-generic-interface-virtualTagNode.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<node name="mpls">
  <properties>
    <help>Show MPLS information</help>
  </properties>
  <children>
  #include <include/ldp-sync.xml.i>
  </children>
</node>
<node name="mpls-te">
  <properties>
    <help>Show MPLS traffic engineering information</help>
  </properties>
  <children>
    <leafNode name="router">
      <properties>
        <help>Show router information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <tagNode name="interface">
      <properties>
        <help>Show information about specific interface</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces</script>
        </completionHelp>
      </properties>
      <standalone>
        <help>Show interface information</help>
        <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      </standalone>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </tagNode>
  </children>
</node>
<node name="neighbor">
  <properties>
    <help>Show IS-IS neighbor adjacencies</help>
  </properties>
  <children>
    <virtualTagNode>
      <properties>
        <help>Show specific IS-IS neighbor adjacency </help>
        <completionHelp>
          <list>system-id</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </virtualTagNode>
    #include <include/vtysh-generic-detail.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<node name="route">
  <properties>
    <help>Show IS-IS routing table</help>
  </properties>
  <children>
    <leafNode name="level-1">
      <properties>
        <help>Show level-1 routes</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="level-2">
      <properties>
        <help>Show level-2 routes</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="prefix-sid">
     <properties>
       <help>Show Prefix-SID information</help>
     </properties>
     <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
   </leafNode>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<node name="segment-routing">
  <properties>
    <help>Show IS-IS Segment-Routing (SPRING) information</help>
  </properties>
  <children>
    <leafNode name="node">
      <properties>
        <help>Show node information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
</node>
<leafNode name="spf-delay-ietf">
  <properties>
    <help>Show IS-IS SPF delay parameters</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<leafNode name="summary">
  <properties>
    <help>Show IS-IS information summary</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<node name="topology">
  <properties>
    <help>Show IS-IS paths to Intermediate Systems</help>
  </properties>
  <children>
    <leafNode name="level-1">
      <properties>
        <help>Show level-1 routes</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="level-2">
      <properties>
        <help>Show level-2 routes</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<!-- included end -->
