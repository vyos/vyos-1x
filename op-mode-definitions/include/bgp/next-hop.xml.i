<!-- included start from bgp/next-hop.xml.i -->
<node name="nexthop">
  <properties>
    <help>Show BGP nexthop table</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/vtysh-generic-detail.xml.i>
  </children>
</node>
<tagNode name="nexthop">
  <properties>
    <help>IPv4/IPv6 nexthop address</help>
    <completionHelp>
      <list>&lt;x.x.x.x&gt; &lt;h:h:h:h:h:h:h:h&gt;</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    #include <include/vtysh-generic-detail.xml.i>
  </children>
</tagNode>
<!-- included end -->
