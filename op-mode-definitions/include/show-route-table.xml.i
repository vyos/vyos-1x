<!-- included start from show-route-table.xml.i -->
<node name="table">
  <properties>
    <help>Table to display</help>
  </properties>
</node>
<tagNode name="table">
  <properties>
    <help>The table number to display</help>
    <completionHelp>
      <list>all</list>
      <path>protocols static table</path>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<!-- included end -->
