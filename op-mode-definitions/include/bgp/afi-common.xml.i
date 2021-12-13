<!-- included start from bgp/afi-common.xml.i -->
<tagNode name="community">
  <properties>
    <help>Community number where AA and NN are (0-65535)</help>
    <completionHelp>
      <list>AA:NN</list>
    </completionHelp>
  </properties>
  <children>
    #include <include/bgp/exact-match.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<tagNode name="large-community">
  <properties>
    <help>Display routes matching the large-communities</help>
    <completionHelp>
      <list>AA:BB:CC</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/bgp/exact-match.xml.i>
  </children>
</tagNode>
<tagNode name="large-community-list">
  <properties>
    <help>Display routes matching the large-community-list</help>
    <completionHelp>
      <path>policy large-community-list</path>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/bgp/exact-match.xml.i>
  </children>
</tagNode>
<leafNode name="statistics">
  <properties>
    <help>RIB advertisement statistics</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<node name="summary">
  <properties>
    <help>Summary of BGP neighbor status</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <leafNode name="established">
      <properties>
        <help>Show only sessions in Established state</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="failed">
      <properties>
        <help>Show only sessions not in Established state</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
</node>
<!-- included end -->
