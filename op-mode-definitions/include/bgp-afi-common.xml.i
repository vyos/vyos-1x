<!-- included start from bgp-afi-common.xml.i -->
<tagNode name="community">
  <properties>
    <help>Community number where AA and NN are (0-65535)</help>
    <completionHelp>
      <list>AA:NN</list>
    </completionHelp>
  </properties>
  <children>
    <leafNode name="exact-match">
      <properties>
        <help>Exact match of the communities</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<tagNode name="large-community">
  <properties>
    <help>List of large-community numbers</help>
    <completionHelp>
      <list>AA:BB:CC</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<leafNode name="statistics">
  <properties>
    <help>RIB advertisement statistics</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<leafNode name="summary">
  <properties>
    <help>Summary of BGP neighbor status</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<!-- included end -->
