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
    #include <include/bgp/afi-ipv4-ipv6-flowspec.xml.i>
    #include <include/bgp/afi-ipv4-ipv6-vpn.xml.i>
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
    #include <include/bgp/afi-ipv4-ipv6-vpn.xml.i>
  </children>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
</node>
<node name="l2vpn">
  <properties>
    <help>Layer 2 Virtual Private Network</help>
  </properties>
  <children>
    <tagNode name="evpn">
      <properties>
        <help>Network in the BGP routing table to display</help>
        <completionHelp>
          <list>&lt;x.x.x.x&gt; &lt;x.x.x.x/x&gt; &lt;h:h:h:h:h:h:h:h&gt; &lt;h:h:h:h:h:h:h:h/x&gt;</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </tagNode>
    <node name="evpn">
      <properties>
        <help>Ethernet Virtual Private Network</help>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
      <children>
        #include <include/bgp/afi-common.xml.i>
        <node name="all">
          <properties>
            <help>Display information about all EVPN NLRIs</help>
          </properties>
          <children>
            <leafNode name="overlay">
              <properties>
                <help>Display BGP Overlay Information for prefixes</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
            <leafNode name="tags">
              <properties>
                <help>Display BGP tags for prefixes</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </node>
        <node name="es">
          <properties>
            <help>Ethernet Segment</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            #include <include/vtysh-generic-detail.xml.i>
          </children>
        </node>
        <node name="es-evi">
          <properties>
            <help>Ethernet Segment per EVI</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            #include <include/vtysh-generic-detail.xml.i>
            #include <include/vni-tagnode.xml.i>
          </children>
        </node>
        <leafNode name="import-rt">
          <properties>
            <help>Show import route target</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </leafNode>
        <tagNode name="neighbors">
          <properties>
            <help>Show detailed BGP neighbor information</help>
            <completionHelp>
              <script>vtysh -c 'show bgp summary' | awk '{print $1'} | grep -e '^[0-9a-f]'</script>
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
            <leafNode name="routes">
              <properties>
                <help>Show routes learned from BGP neighbor</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </tagNode>
        <tagNode name="rd">
          <properties>
            <help>Show detailed BGP neighbor information</help>
            <completionHelp>
              <list>ASN:NN IPADDRESS:NN</list>
            </completionHelp>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            <leafNode name="overlay">
              <properties>
                <help>Display BGP Overlay Information for prefixes</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
            <leafNode name="tags">
              <properties>
                <help>Display BGP tags for prefixes</help>
              </properties>
              <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
            </leafNode>
          </children>
        </tagNode>
        <node name="route">
          <properties>
            <help>EVPN route information</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
          <children>
            #include <include/vtysh-generic-detail.xml.i>
            <node name="type">
              <properties>
                <help>Specify Route type</help>
              </properties>
              <children>
                <leafNode name="1">
                  <properties>
                    <help>EAD (Type-1) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="2">
                  <properties>
                    <help>MAC-IP (Type-2) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="3">
                  <properties>
                    <help>Multicast (Type-3) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="4">
                  <properties>
                    <help>Ethernet Segment (Type-4) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="5">
                  <properties>
                    <help>Prefix (Type-5) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="ead">
                  <properties>
                    <help>EAD (Type-1) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="es">
                  <properties>
                    <help>Ethernet Segment (Type-4) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="macip">
                  <properties>
                    <help>MAC-IP (Type-2) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="multicast">
                  <properties>
                    <help>Multicast (Type-3) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
                <leafNode name="prefix">
                  <properties>
                    <help>Prefix (Type-5) route</help>
                  </properties>
                  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
                </leafNode>
              </children>
            </node>
            #include <include/vni-tagnode-all.xml.i>
          </children>
        </node>
        #include <include/vni-tagnode.xml.i>
        <leafNode name="vni">
          <properties>
            <help>VXLAN network identifier (VNI)</help>
          </properties>
          <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- included end -->
