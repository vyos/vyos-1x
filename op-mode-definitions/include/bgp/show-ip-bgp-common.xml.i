<!-- included start from bgp/show-ip-bgp-common.xml.i -->
<leafNode name="attribute-info">
  <properties>
    <help>Show BGP attribute information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<leafNode name="cidr-only">
  <properties>
    <help>Display only routes with non-natural netmasks</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<leafNode name="community-info">
  <properties>
    <help>List all bgp community information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
#include <include/bgp/afi-common.xml.i>
#include <include/bgp/afi-ipv4-ipv6-common.xml.i>
<tagNode name="prefix-list">
  <properties>
    <completionHelp>
      <path>policy prefix-list</path>
    </completionHelp>
  </properties>
</tagNode>
<node name="ipv4">
  <properties>
    <help>Show BGP IPv4 information</help>
  </properties>
  <children>
    <node name="unicast">
      <properties>
        <help>Show BGP IPv4 unicast information</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        <virtualTagNode>
          <properties>
            <help>Show BGP information for specified IP address or prefix</help>
            <completionHelp>
              <list>&lt;x.x.x.x&gt; &lt;x.x.x.x/x&gt;</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </virtualTagNode>
        <leafNode name="cidr-only">
          <properties>
            <help>Display only routes with non-natural netmasks</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </leafNode>
        <tagNode name="community">
          <properties>
            <help>Display routes matching the specified communities</help>
            <completionHelp>
              <list>&lt;AA:NN&gt; local-AS no-advertise no-export</list>
            </completionHelp>
          </properties>
          <standalone>
            <help>Show BGP routes matching the communities</help>
            <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          </standalone>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
        <tagNode name="community-list">
          <properties>
            <help>Show BGP routes matching specified community list</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <leafNode name="exact-match">
            <properties>
              <help>Show BGP routes exactly matching specified community list</help>
            </properties>
            <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </tagNode>
        <tagNode name="neighbors">
          <properties>
            <help>Show detailed BGP IPv4 unicast neighbor information</help>
            <completionHelp>
              <script>vtysh -c "show ip bgp ipv4 unicast summary" | awk '{print $1}' | grep -oE "\b([0-9]{1,3}\.){3}[0-9]{1,3}\b"</script>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            #include <include/bgp/advertised-routes.xml.i>
            #include <include/bgp/dampened-routes.xml.i>
            #include <include/bgp/filtered-routes.xml.i>
            #include <include/bgp/flap-statistics.xml.i>
            #include <include/bgp/prefix-counts.xml.i>
            #include <include/bgp/received.xml.i>
            #include <include/bgp/received-routes.xml.i>
            #include <include/bgp/routes.xml.i>
          </children>
        </tagNode>
        <leafNode name="paths">
          <properties>
            <help>Show BGP path information</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </leafNode>
         <tagNode name="prefix-list">
          <properties>
            <help>Show BGP routes matching the specified prefix list</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
        <tagNode name="regexp">
          <properties>
            <help>Show BGP routes matching the specified AS path regular expression</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
        <tagNode name="route-map">
          <properties>
            <help>Show BGP routes matching the specified route map</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </tagNode>
        <leafNode name="summary">
          <properties>
            <help>Show summary of BGP information</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<leafNode name="large-community-info">
  <properties>
    <help>Show BGP large-community information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<leafNode name="memory">
  <properties>
    <help>Show BGP memory usage</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<leafNode name="paths">
  <properties>
    <help>Show BGP path information</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<!-- included end -->
