<!-- included start from ospfv3/linkstate.xml.i -->
<node name="linkstate">
  <properties>
    <help>Show OSPFv3 linkstate routing information</help>
  </properties>
  <children>
    #include <include/frr-detail.xml.i>
    <tagNode name="network">
      <properties>
        <help>Show linkstate Network information</help>
        <completionHelp>
          <list>&lt;x.x.x.x&gt;</list>
        </completionHelp>
      </properties>
      <children>
        <node name="node.tag">
          <properties>
            <help>Specify Link state ID as IPv4 address notation</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </node>
      </children>
    </tagNode>
    <tagNode name="router">
      <properties>
        <help>Show linkstate Router information</help>
        <completionHelp>
          <list>&lt;x.x.x.x&gt;</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </tagNode>
  </children>
</node>
<!-- included end -->
