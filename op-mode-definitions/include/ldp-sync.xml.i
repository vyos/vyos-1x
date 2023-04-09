<!-- included start from ldp-sync.xml.i -->
<node name="ldp-sync">
  <properties>
    <help>Show LDP-IGP synchronization information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <tagNode name="interface">
      <properties>
        <help>Show specific LDP-IGP synchronization for an interface</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces</script>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </tagNode>
  </children>
</node>
<!-- included end -->