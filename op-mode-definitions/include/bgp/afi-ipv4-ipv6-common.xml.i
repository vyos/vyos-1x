<!-- included start from bgp/afi-ipv4-ipv6-common.xml.i -->
<node name="community">
  <properties>
    <help>Display routes matching the community</help>
  </properties>
  <children>
    <leafNode name="accept-own">
      <properties>
        <help>Should accept local VPN route if exported and imported into different VRF (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="accept-own-nexthop">
      <properties>
        <help>Should accept VPN route with local nexthop (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="blackhole">
      <properties>
        <help>Inform EBGP peers to blackhole traffic to prefix (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    #include <include/bgp/exact-match.xml.i>
    <leafNode name="graceful-shutdown">
      <properties>
        <help>Graceful shutdown (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="llgr-stale">
      <properties>
        <help>Staled Long-lived Graceful Restart VPN route (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="local-AS">
      <properties>
        <help>Do not send outside local AS (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="no-advertise">
      <properties>
        <help>Do not advertise to any peer (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="no-export">
      <properties>
        <help>Do not export to next AS (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="no-llgr">
      <properties>
        <help>Removed because Long-lived Graceful Restart was not enabled for VPN route (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="no-peer">
      <properties>
        <help>Do not export to any peer (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="route-filter-translated-v4">
      <properties>
        <help>RT translated VPNv4 route filtering (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="route-filter-translated-v6">
      <properties>
        <help>RT translated VPNv6 route filtering (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="route-filter-v4">
      <properties>
        <help>RT VPNv4 route filtering (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="route-filter-v6">
      <properties>
        <help>RT VPNv6 route filtering (well-known community)</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<tagNode name="community-list">
  <properties>
    <help>Display routes matching the community-list</help>
    <completionHelp>
      <list>1-500 name</list>
    </completionHelp>
  </properties>
  <children>
    #include <include/bgp/exact-match.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<node name="dampening">
  <properties>
    <help>Display detailed information about dampening</help>
  </properties>
  <children>
    <leafNode name="dampened-paths">
      <properties>
        <help>Display paths suppressed due to dampening</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="flap-statistics">
      <properties>
        <help>Display flap statistics of routes</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="parameters">
      <properties>
        <help>Display detail of configured dampening parameters</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
</node>
<tagNode name="filter-list">
  <properties>
    <help>Display routes conforming to the filter-list</help>
    <completionHelp>
      <script>vtysh -c 'show bgp as-path-access-list' | grep 'AS path access list' | awk '{print $NF}'</script>
    </completionHelp>
  </properties>
</tagNode>
<node name="large-community">
  <properties>
    <help>Show BGP routes matching the specified large-communities</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<leafNode name="neighbors">
  <properties>
    <help>Detailed information on TCP and BGP neighbor connections</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</leafNode>
<tagNode name="neighbors">
  <properties>
    <help>Show BGP information for specified neighbor</help>
    <completionHelp>
      <script>vtysh -c "$(IFS=$' '; echo "${COMP_WORDS[@]:0:${#COMP_WORDS[@]}-2} summary")" |  awk '/^[0-9a-f]/ {print $1}'</script>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <leafNode name="advertised-routes">
      <properties>
        <help>Show routes advertised to a BGP neighbor</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="dampened-routes">
      <properties>
        <help>Show dampened routes received from BGP neighbor</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="flap-statistics">
      <properties>
        <help>Show flap statistics of the routes learned from BGP neighbor</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="prefix-counts">
      <properties>
        <help>Show detailed prefix count information for BGP neighbor</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <node name="received">
      <properties>
        <help>Show information received from BGP neighbor</help>
      </properties>
      <children>
        <leafNode name="prefix-filter">
          <properties>
            <help>Show prefixlist filter</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </leafNode>
      </children>
    </node>
    <leafNode name="filtered-routes">
      <properties>
        <help>Show filtered routes from BGP neighbor</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="received-routes">
      <properties>
        <help>Show received routes from BGP neighbor</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
    <leafNode name="routes">
      <properties>
        <help>Show routes learned from BGP neighbor</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </leafNode>
  </children>
</tagNode>
<tagNode name="prefix-list">
  <properties>
    <help>Display routes conforming to the prefix-list</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<tagNode name="regexp">
  <properties>
    <help>Display routes matching the AS path regular expression</help>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<tagNode name="route-map">
  <properties>
    <help>Show BGP routes matching the specified route map</help>
    <completionHelp>
      <path>policy route-map</path>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
#include <include/vtysh-generic-wide.xml.i>
<!-- included end -->
