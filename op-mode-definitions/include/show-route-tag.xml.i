<!-- included start from show-route-tag.xml.i -->
<node name="tag">
  <properties>
    <help>Show only routes with tag</help>
  </properties>
</node>
<tagNode name="tag">
  <properties>
    <help>Tag value</help>
    <completionHelp>
      <list>&lt;1-4294967295&gt;</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<!-- included end -->
