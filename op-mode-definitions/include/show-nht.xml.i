<!-- included start from show-nht.xml.i -->
<node name="nht">
  <properties>
    <help>Show Nexthop tracking table</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <tagNode name="vrf">
      <properties>
        <help>Specify the VRF</help>
        <completionHelp>
          <path>vrf name</path>
          <list>all default</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </tagNode>
  </children>
</node>
<!-- included end -->
