<!-- included start from bgp/show-bgp-common.xml.i -->
#include <include/bgp/afi-common.xml.i>
#include <include/bgp/afi-ipv4-ipv6-common.xml.i>
<tagNode name="ipv4">
  <properties>
    <help>Network in the BGP routing table to display</help>
    <completionHelp>
      <list>&lt;x.x.x.x&gt; &lt;x.x.x.x/x&gt; &lt;h:h:h:h:h:h:h:h&gt; &lt;h:h:h:h:h:h:h:h/x&gt;</list>
    </completionHelp>
  </properties>
  <children>
    #include <include/bgp/prefix-bestpath-multipath.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<node name="ipv4">
  <properties>
    <help>IPv4 Address Family</help>
  </properties>
  <children>
    #include <include/bgp/afi-common.xml.i>
    #include <include/bgp/afi-ipv4-ipv6-common.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<tagNode name="ipv6">
  <properties>
    <help>Network in the BGP routing table to display</help>
    <completionHelp>
      <list>&lt;x.x.x.x&gt; &lt;x.x.x.x/x&gt; &lt;h:h:h:h:h:h:h:h&gt; &lt;h:h:h:h:h:h:h:h/x&gt;</list>
    </completionHelp>
  </properties>
  <children>
    #include <include/bgp/prefix-bestpath-multipath.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</tagNode>
<node name="ipv6">
  <properties>
    <help>IPv6 Address Family</help>
  </properties>
  <children>
    #include <include/bgp/afi-common.xml.i>
    #include <include/bgp/afi-ipv4-ipv6-common.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<!-- included end -->
