<!-- included start from isis-common.xml.i -->
<node name="database">
  <properties>
    <help>Show IS-IS link state database</help>
  </properties>
  <children>
    <leafNode name="detail">
      <properties>
        <help>Show detailed information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<tagNode name="database">
  <properties>
    <help>Show IS-IS link state database PDU</help>
    <completionHelp>
      <list>lsp-id detail</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
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
      <script>${vyos_completion_dir}/list_interfaces.py</script>
    </completionHelp>
  </properties>
  <children>
    <leafNode name="detail">
      <properties>
        <help>Show detailed information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<tagNode name="interface">
  <properties>
    <help>Show specific IS-IS interface</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces.py</script>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<node name="mpls-te">
  <properties>
    <help>Show IS-IS MPLS traffic engineering information</help>
  </properties>
  <children>
    <leafNode name="router">
      <properties>
        <help>Show router information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="interface">
      <properties>
        <help>Show interface information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <tagNode name="interface">
      <properties>
        <help>Show specific IS-IS interface</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces.py</script>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </tagNode>
  </children>
</node>
<node name="neighbor">
  <properties>
    <help>Show IS-IS neighbor adjacencies</help>
  </properties>
  <children>
    <leafNode name="detail">
      <properties>
        <help>Show detailed information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
  <command>vtysh -c "show isis neighbor"</command>
</node>
<tagNode name="neighbor">
  <properties>
    <help>Show specific IS-IS neighbor adjacency </help>
    <completionHelp>
      <list>system-id</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
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
  </children>
  <command>vtysh -c "show isis route"</command>
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
    <leafNode name="prefix-sids">
      <properties>
        <help>Show prefix segment IDs</help>
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
