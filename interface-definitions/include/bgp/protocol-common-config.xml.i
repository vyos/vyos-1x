<!-- include start from bgp/protocol-common-config.xml.i -->
<node name="address-family">
  <properties>
    <help>BGP address-family parameters</help>
  </properties>
  <children>
    <node name="ipv4-unicast">
      <properties>
        <help>IPv4 BGP settings</help>
      </properties>
      <children>
        <tagNode name="aggregate-address">
          <properties>
            <help>BGP aggregate network</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>BGP aggregate network</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-aggregate-address.xml.i>
          </children>
        </tagNode>
        <node name="distance">
          <properties>
            <help>Administrative distances for BGP routes</help>
          </properties>
          <children>
            <leafNode name="external">
              <properties>
                <help>eBGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>eBGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="internal">
              <properties>
                <help>iBGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>iBGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="local">
              <properties>
                <help>Locally originated BGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>Locally originated BGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <tagNode name="prefix">
              <properties>
                <help>Administrative distance for a specific BGP prefix</help>
                <valueHelp>
                  <format>ipv4net</format>
                  <description>Administrative distance for a specific BGP prefix</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv4-prefix"/>
                </constraint>
              </properties>
              <children>
                <leafNode name="distance">
                  <properties>
                    <help>Administrative distance for prefix</help>
                    <valueHelp>
                      <format>u32:1-255</format>
                      <description>Administrative distance for external BGP routes</description>
                    </valueHelp>
                    <constraint>
                      <validator name="numeric" argument="--range 1-255"/>
                    </constraint>
                  </properties>
                </leafNode>
              </children>
            </tagNode>
          </children>
        </node>
        #include <include/bgp/afi-export-import.xml.i>
        #include <include/bgp/afi-label.xml.i>
        #include <include/bgp/afi-maximum-paths.xml.i>
        <tagNode name="network">
          <properties>
            <help>BGP network</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>BGP network</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
          <children>
            <leafNode name="backdoor">
              <properties>
                <help>Network as a backdoor route</help>
                <valueless/>
              </properties>
            </leafNode>
            #include <include/route-map.xml.i>
          </children>
        </tagNode>
        #include <include/bgp/afi-rd.xml.i>
        #include <include/bgp/afi-route-map-vpn.xml.i>
        #include <include/bgp/afi-route-target-vpn.xml.i>
        <node name="redistribute">
          <properties>
            <help>Redistribute routes from other protocols into BGP</help>
          </properties>
          <children>
            <node name="connected">
              <properties>
                <help>Redistribute connected routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="isis">
              <properties>
                <help>Redistribute IS-IS routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="kernel">
              <properties>
                <help>Redistribute kernel routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="ospf">
              <properties>
                <help>Redistribute OSPF routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="rip">
              <properties>
                <help>Redistribute RIP routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="static">
              <properties>
                <help>Redistribute static routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <leafNode name="table">
              <properties>
                <help>Redistribute non-main Kernel Routing Table</help>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
    <node name="ipv4-multicast">
      <properties>
        <help>Multicast IPv4 BGP settings</help>
      </properties>
      <children>
        <tagNode name="aggregate-address">
          <properties>
            <help>BGP aggregate network/prefix</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>BGP aggregate network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-aggregate-address.xml.i>
          </children>
        </tagNode>
        <node name="distance">
          <properties>
            <help>Administrative distances for BGP routes</help>
          </properties>
          <children>
            <leafNode name="external">
              <properties>
                <help>eBGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>eBGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="internal">
              <properties>
                <help>iBGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>iBGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="local">
              <properties>
                <help>Locally originated BGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>Locally originated BGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <tagNode name="prefix">
              <properties>
                <help>Administrative distance for a specific BGP prefix</help>
                <valueHelp>
                  <format>ipv4net</format>
                  <description>Administrative distance for a specific BGP prefix</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv4-prefix"/>
                </constraint>
              </properties>
              <children>
                <leafNode name="distance">
                  <properties>
                    <help>Administrative distance for prefix</help>
                    <valueHelp>
                      <format>u32:1-255</format>
                      <description>Administrative distance for external BGP routes</description>
                    </valueHelp>
                    <constraint>
                      <validator name="numeric" argument="--range 1-255"/>
                    </constraint>
                  </properties>
                </leafNode>
              </children>
            </tagNode>
          </children>
        </node>
        <tagNode name="network">
          <properties>
            <help>Import BGP network/prefix into multicast IPv4 RIB</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>Multicast IPv4 BGP network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
          <children>
            <leafNode name="backdoor">
              <properties>
                <help>Use BGP network/prefix as a backdoor route</help>
                <valueless/>
              </properties>
            </leafNode>
            #include <include/route-map.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
    <node name="ipv4-labeled-unicast">
      <properties>
        <help>Labeled Unicast IPv4 BGP settings</help>
      </properties>
      <children>
        <tagNode name="aggregate-address">
          <properties>
            <help>BGP aggregate network/prefix</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>BGP aggregate network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-aggregate-address.xml.i>
          </children>
        </tagNode>
        <tagNode name="network">
          <properties>
            <help>Import BGP network/prefix into labeled unicast IPv4 RIB</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>Labeled Unicast IPv4 BGP network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
          <children>
            <leafNode name="backdoor">
              <properties>
                <help>Use BGP network/prefix as a backdoor route</help>
                <valueless/>
              </properties>
            </leafNode>
            #include <include/route-map.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
    <node name="ipv4-flowspec">
      <properties>
        <help>Flowspec IPv4 BGP settings</help>
      </properties>
      <children>
        <node name="local-install">
          <properties>
            <help>Apply local policy routing to interface</help>
          </properties>
          <children>
            <leafNode name="interface">
              <properties>
                <help>Interface</help>
                <completionHelp>
                  <script>${vyos_completion_dir}/list_interfaces.py</script>
                </completionHelp>
                <multi/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
    <node name="ipv4-vpn">
      <properties>
        <help>Unicast VPN IPv4 BGP settings</help>
      </properties>
      <children>
        <tagNode name="network">
          <properties>
            <help>Import BGP network/prefix into unicast VPN IPv4 RIB</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>Unicast VPN IPv4 BGP network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/route-distinguisher.xml.i>
            <leafNode name="label">
              <properties>
                <help>MPLS label value assigned to route</help>
                <valueHelp>
                  <format>u32:0-1048575</format>
                  <description>MPLS label value</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 0-1048575"/>
                </constraint>
              </properties>
            </leafNode>
          </children>
        </tagNode>
      </children>
    </node>
    <node name="ipv6-unicast">
      <properties>
        <help>IPv6 BGP settings</help>
      </properties>
      <children>
        <tagNode name="aggregate-address">
          <properties>
            <help>BGP aggregate network</help>
            <valueHelp>
              <format>ipv6net</format>
              <description>Aggregate network</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-aggregate-address.xml.i>
          </children>
        </tagNode>
        <node name="distance">
          <properties>
            <help>Administrative distances for BGP routes</help>
          </properties>
          <children>
            <leafNode name="external">
              <properties>
                <help>eBGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>eBGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="internal">
              <properties>
                <help>iBGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>iBGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="local">
              <properties>
                <help>Locally originated BGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>Locally originated BGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <tagNode name="prefix">
              <properties>
                <help>Administrative distance for a specific BGP prefix</help>
                <valueHelp>
                  <format>ipv6net</format>
                  <description>Administrative distance for a specific BGP prefix</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv6-prefix"/>
                </constraint>
              </properties>
              <children>
                <leafNode name="distance">
                  <properties>
                    <help>Administrative distance for prefix</help>
                    <valueHelp>
                      <format>u32:1-255</format>
                      <description>Administrative distance for external BGP routes</description>
                    </valueHelp>
                    <constraint>
                      <validator name="numeric" argument="--range 1-255"/>
                    </constraint>
                  </properties>
                </leafNode>
              </children>
            </tagNode>
          </children>
        </node>
        #include <include/bgp/afi-export-import.xml.i>
        #include <include/bgp/afi-label.xml.i>
        #include <include/bgp/afi-maximum-paths.xml.i>
        <tagNode name="network">
          <properties>
            <help>BGP network</help>
            <valueHelp>
              <format>ipv6net</format>
              <description>Aggregate network</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-path-limit.xml.i>
            #include <include/route-map.xml.i>
          </children>
        </tagNode>
        #include <include/bgp/afi-rd.xml.i>
        #include <include/bgp/afi-route-map-vpn.xml.i>
        #include <include/bgp/afi-route-target-vpn.xml.i>
        <node name="redistribute">
          <properties>
            <help>Redistribute routes from other protocols into BGP</help>
          </properties>
          <children>
            <node name="connected">
              <properties>
                <help>Redistribute connected routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="kernel">
              <properties>
                <help>Redistribute kernel routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="ospfv3">
              <properties>
                <help>Redistribute OSPFv3 routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="ripng">
              <properties>
                <help>Redistribute RIPng routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <node name="static">
              <properties>
                <help>Redistribute static routes into BGP</help>
              </properties>
              <children>
                #include <include/bgp/afi-redistribute-metric-route-map.xml.i>
              </children>
            </node>
            <leafNode name="table">
              <properties>
                <help>Redistribute non-main Kernel Routing Table</help>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
    <node name="ipv6-multicast">
      <properties>
        <help>Multicast IPv6 BGP settings</help>
      </properties>
      <children>
        <tagNode name="aggregate-address">
          <properties>
            <help>BGP aggregate network/prefix</help>
            <valueHelp>
              <format>ipv6net</format>
              <description>BGP aggregate network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-aggregate-address.xml.i>
          </children>
        </tagNode>
        <node name="distance">
          <properties>
            <help>Administrative distances for BGP routes</help>
          </properties>
          <children>
            <leafNode name="external">
              <properties>
                <help>eBGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>eBGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="internal">
              <properties>
                <help>iBGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>iBGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="local">
              <properties>
                <help>Locally originated BGP routes administrative distance</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>Locally originated BGP routes administrative distance</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <tagNode name="prefix">
              <properties>
                <help>Administrative distance for a specific BGP prefix</help>
                <valueHelp>
                  <format>ipv6net</format>
                  <description>Administrative distance for a specific BGP prefix</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv6-prefix"/>
                </constraint>
              </properties>
              <children>
                <leafNode name="distance">
                  <properties>
                    <help>Administrative distance for prefix</help>
                    <valueHelp>
                      <format>u32:1-255</format>
                      <description>Administrative distance for external BGP routes</description>
                    </valueHelp>
                    <constraint>
                      <validator name="numeric" argument="--range 1-255"/>
                    </constraint>
                  </properties>
                </leafNode>
              </children>
            </tagNode>
          </children>
        </node>
        <tagNode name="network">
          <properties>
            <help>Import BGP network/prefix into multicast IPv6 RIB</help>
            <valueHelp>
              <format>ipv6net</format>
              <description>Multicast IPv6 BGP network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-path-limit.xml.i>
            #include <include/route-map.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
    <node name="ipv6-labeled-unicast">
      <properties>
        <help>Labeled Unicast IPv6 BGP settings</help>
      </properties>
      <children>
        <tagNode name="aggregate-address">
          <properties>
            <help>BGP aggregate network/prefix</help>
            <valueHelp>
              <format>ipv6net</format>
              <description>BGP aggregate network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-aggregate-address.xml.i>
          </children>
        </tagNode>
        <tagNode name="network">
          <properties>
            <help>Import BGP network/prefix into labeled unicast IPv6 RIB</help>
            <valueHelp>
              <format>ipv6net</format>
              <description>Labeled Unicast IPv6 BGP network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-prefix"/>
            </constraint>
          </properties>
          <children>
            <leafNode name="backdoor">
              <properties>
                <help>Use BGP network/prefix as a backdoor route</help>
                <valueless/>
              </properties>
            </leafNode>
            #include <include/route-map.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
    <node name="ipv6-flowspec">
      <properties>
        <help>Flowspec IPv6 BGP settings</help>
      </properties>
      <children>
        <node name="local-install">
          <properties>
            <help>Apply local policy routing to interface</help>
          </properties>
          <children>
            <leafNode name="interface">
              <properties>
                <help>Interface</help>
                <completionHelp>
                  <script>${vyos_completion_dir}/list_interfaces.py</script>
                </completionHelp>
                <multi/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
    <node name="ipv6-vpn">
      <properties>
        <help>Unicast VPN IPv6 BGP settings</help>
      </properties>
      <children>
        <tagNode name="network">
          <properties>
            <help>Import BGP network/prefix into unicast VPN IPv6 RIB</help>
            <valueHelp>
              <format>ipv6net</format>
              <description>Unicast VPN IPv6 BGP network/prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-prefix"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/route-distinguisher.xml.i>
            <leafNode name="label">
              <properties>
                <help>MPLS label value assigned to route</help>
                <valueHelp>
                  <format>u32:0-1048575</format>
                  <description>MPLS label value</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 0-1048575"/>
                </constraint>
              </properties>
            </leafNode>
          </children>
        </tagNode>
      </children>
    </node>
    <node name="l2vpn-evpn">
      <properties>
        <help>L2VPN EVPN BGP settings</help>
      </properties>
      <children>
        <node name="advertise">
          <properties>
            <help>Advertise prefix routes</help>
          </properties>
          <children>
            <node name="ipv4">
              <properties>
                <help>IPv4 address family</help>
              </properties>
              <children>
                #include <include/bgp/afi-l2vpn-advertise.xml.i>
              </children>
            </node>
            <node name="ipv6">
              <properties>
                <help>IPv6 address family</help>
              </properties>
              <children>
                #include <include/bgp/afi-l2vpn-advertise.xml.i>
              </children>
            </node>
          </children>
        </node>
        <leafNode name="advertise-all-vni">
          <properties>
            <help>Advertise All local VNIs</help>
            <valueless/>
          </properties>
        </leafNode>
        #include <include/bgp/afi-l2vpn-common.xml.i>
        <leafNode name="advertise-pip">
          <properties>
            <help>EVPN system primary IP</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IP address</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-address"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="rt-auto-derive">
          <properties>
            <help>Auto derivation of Route Target (RFC8365)</help>
            <valueless/>
          </properties>
        </leafNode>
        <node name="flooding">
          <properties>
            <help>Specify handling for BUM packets</help>
          </properties>
          <children>
            <leafNode name="disable">
              <properties>
                <help>Do not flood any BUM packets</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="head-end-replication">
              <properties>
                <help>Flood BUM packets using head-end replication</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
        <tagNode name="vni">
          <properties>
            <help>VXLAN Network Identifier</help>
            <valueHelp>
              <format>u32:1-16777215</format>
              <description>VNI number</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-16777215"/>
            </constraint>
          </properties>
          <children>
            #include <include/bgp/afi-l2vpn-common.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
  </children>
</node>
<node name="listen">
  <properties>
    <help>Listen for and accept BGP dynamic neighbors from range</help>
  </properties>
  <children>
    <leafNode name="limit">
      <properties>
        <help>Maximum number of dynamic neighbors that can be created</help>
        <valueHelp>
          <format>u32:1-5000</format>
          <description>BGP neighbor limit</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-5000"/>
        </constraint>
      </properties>
    </leafNode>
    <tagNode name="range">
      <properties>
        <help>BGP dynamic neighbors listen range</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 dynamic neighbors listen range</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6net</format>
          <description>IPv6 dynamic neighbors listen range</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-prefix"/>
          <validator name="ipv6-prefix"/>
        </constraint>
      </properties>
      <children>
        #include <include/bgp/peer-group.xml.i>
      </children>
    </tagNode>
  </children>
</node>
<leafNode name="system-as">
  <properties>
    <help>Autonomous System Number (ASN)</help>
    <valueHelp>
      <format>u32:1-4294967294</format>
      <description>Autonomous System Number</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967294"/>
    </constraint>
  </properties>
</leafNode>
<tagNode name="neighbor">
  <properties>
    <help>BGP neighbor</help>
    <valueHelp>
      <format>ipv4</format>
      <description>BGP neighbor IP address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>BGP neighbor IPv6 address</description>
    </valueHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv6-address"/>
      <validator name="interface-name"/>
    </constraint>
  </properties>
  <children>
    <node name="address-family">
      <properties>
        <help>Address-family parameters</help>
      </properties>
      <children>
        #include <include/bgp/neighbor-afi-ipv4-unicast.xml.i>
        #include <include/bgp/neighbor-afi-ipv6-unicast.xml.i>
        #include <include/bgp/neighbor-afi-ipv4-labeled-unicast.xml.i>
        #include <include/bgp/neighbor-afi-ipv6-labeled-unicast.xml.i>
        #include <include/bgp/neighbor-afi-ipv4-vpn.xml.i>
        #include <include/bgp/neighbor-afi-ipv6-vpn.xml.i>
        #include <include/bgp/neighbor-afi-ipv4-flowspec.xml.i>
        #include <include/bgp/neighbor-afi-ipv6-flowspec.xml.i>
        #include <include/bgp/neighbor-afi-ipv4-multicast.xml.i>
        #include <include/bgp/neighbor-afi-ipv6-multicast.xml.i>
        #include <include/bgp/neighbor-afi-l2vpn-evpn.xml.i>
      </children>
    </node>
    <leafNode name="advertisement-interval">
      <properties>
        <help>Minimum interval for sending routing updates</help>
        <valueHelp>
          <format>u32:0-600</format>
          <description>Advertisement interval in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-600"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/generic-description.xml.i>
    #include <include/bgp/neighbor-bfd.xml.i>
    #include <include/bgp/neighbor-capability.xml.i>
    #include <include/bgp/neighbor-disable-capability-negotiation.xml.i>
    #include <include/bgp/neighbor-disable-connected-check.xml.i>
    #include <include/bgp/neighbor-ebgp-multihop.xml.i>
    #include <include/bgp/neighbor-graceful-restart.xml.i>
    <node name="interface">
      <properties>
        <help>Interface parameters</help>
      </properties>
      <children>
        #include <include/bgp/peer-group.xml.i>
        #include <include/bgp/remote-as.xml.i>
        #include <include/source-interface.xml.i>
        <node name="v6only">
          <properties>
            <help>Enable BGP with v6 link-local only</help>
          </properties>
          <children>
            #include <include/bgp/peer-group.xml.i>
            #include <include/bgp/remote-as.xml.i>
          </children>
        </node>
      </children>
    </node>
    #include <include/bgp/neighbor-local-as.xml.i>
    #include <include/bgp/neighbor-override-capability.xml.i>
    #include <include/bgp/neighbor-passive.xml.i>
    #include <include/bgp/neighbor-password.xml.i>
    #include <include/bgp/peer-group.xml.i>
    <leafNode name="port">
      <properties>
        <help>Neighbor BGP port</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Neighbor BGP port number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/bgp/remote-as.xml.i>
    #include <include/bgp/neighbor-shutdown.xml.i>
    <leafNode name="solo">
      <properties>
        <help>Do not send back prefixes learned from the neighbor</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="strict-capability-match">
      <properties>
        <help>Enable strict capability negotiation</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="timers">
      <properties>
        <help>Neighbor timers</help>
      </properties>
      <children>
        <leafNode name="connect">
          <properties>
            <help>BGP connect timer for this neighbor</help>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Connect timer in seconds</description>
            </valueHelp>
            <valueHelp>
              <format>0</format>
              <description>Disable connect timer</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-65535"/>
            </constraint>
          </properties>
        </leafNode>
        #include <include/bgp/timers-holdtime.xml.i>
        #include <include/bgp/timers-keepalive.xml.i>
      </children>
    </node>
    #include <include/bgp/neighbor-ttl-security.xml.i>
    #include <include/bgp/neighbor-update-source.xml.i>
  </children>
</tagNode>
<node name="parameters">
  <properties>
    <help>BGP parameters</help>
  </properties>
  <children>
    <leafNode name="always-compare-med">
      <properties>
        <help>Always compare MEDs from different neighbors</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="bestpath">
      <properties>
        <help>Default bestpath selection mechanism</help>
      </properties>
      <children>
        <node name="as-path">
          <properties>
            <help>AS-path attribute comparison parameters</help>
          </properties>
          <children>
            <leafNode name="confed">
              <properties>
                <help>Compare AS-path lengths including confederation sets and sequences</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="ignore">
              <properties>
                <help>Ignore AS-path length in selecting a route</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="multipath-relax">
              <properties>
                <help>Allow load sharing across routes that have different AS paths (but same length)</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
        <leafNode name="bandwidth">
          <properties>
            <help>Link Bandwidth attribute</help>
            <completionHelp>
              <list>default-weight-for-missing ignore skip-missing</list>
            </completionHelp>
            <valueHelp>
              <format>default-weight-for-missing</format>
              <description>Assign low default weight (1) to paths not having link bandwidth</description>
            </valueHelp>
            <valueHelp>
              <format>ignore</format>
              <description>Ignore link bandwidth (do regular ECMP, not weighted)</description>
            </valueHelp>
            <valueHelp>
              <format>skip-missing</format>
              <description>Ignore paths without link bandwidth for ECMP (if other paths have it)</description>
            </valueHelp>
            <constraint>
              <regex>(default-weight-for-missing|ignore|skip-missing)</regex>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="compare-routerid">
          <properties>
            <help>Compare the router-id for identical EBGP paths</help>
            <valueless/>
          </properties>
        </leafNode>
        <node name="med">
          <properties>
            <help>MED attribute comparison parameters</help>
          </properties>
          <children>
            <leafNode name="confed">
              <properties>
                <help>Compare MEDs among confederation paths</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="missing-as-worst">
              <properties>
                <help>Treat missing route as a MED as the least preferred one</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
        <node name="peer-type">
          <properties>
            <help>Peer type</help>
          </properties>
          <children>
            <leafNode name="multipath-relax">
              <properties>
                <help>Allow load sharing across routes learned from different peer types</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
    <leafNode name="cluster-id">
      <properties>
        <help>Route-reflector cluster-id</help>
        <valueHelp>
          <format>ipv4</format>
          <description>Route-reflector cluster-id</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
    </leafNode>
    <node name="confederation">
      <properties>
        <help>AS confederation parameters</help>
      </properties>
      <children>
        <leafNode name="identifier">
          <properties>
            <help>Confederation AS identifier</help>
            <valueHelp>
              <format>u32:1-4294967294</format>
              <description>Confederation AS id</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-4294967294"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="peers">
          <properties>
            <help>Peer ASs in the BGP confederation</help>
            <valueHelp>
              <format>u32:1-4294967294</format>
              <description>Peer AS number</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-4294967294"/>
            </constraint>
            <multi/>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="conditional-advertisement">
      <properties>
        <help>Conditional advertisement settings</help>
      </properties>
      <children>
        <leafNode name="timer">
          <properties>
            <help>Set period to rescan BGP table to check if condition is met</help>
            <valueHelp>
              <format>u32:5-240</format>
              <description>Period to rerun the conditional advertisement scanner process</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 5-240"/>
            </constraint>
          </properties>
          <defaultValue>60</defaultValue>
        </leafNode>
      </children>
    </node>
    <node name="dampening">
      <properties>
        <help>Enable route-flap dampening</help>
      </properties>
      <children>
        <leafNode name="half-life">
          <properties>
            <help>Half-life time for dampening</help>
            <valueHelp>
              <format>u32:1-45</format>
              <description>Half-life penalty in minutes</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-45"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="max-suppress-time">
          <properties>
            <help>Maximum duration to suppress a stable route</help>
            <valueHelp>
              <format>u32:1-255</format>
              <description>Maximum suppress duration in minutes</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-255"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="re-use">
          <properties>
            <help>Threshold to start reusing a route</help>
            <valueHelp>
              <format>u32:1-20000</format>
              <description>Re-use penalty points</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-20000"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="start-suppress-time">
          <properties>
            <help>When to start suppressing a route</help>
            <valueHelp>
              <format>u32:1-20000</format>
              <description>Start-suppress penalty points</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-20000"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="default">
      <properties>
        <help>BGP defaults</help>
      </properties>
      <children>
        <leafNode name="local-pref">
          <properties>
            <help>Default local preference</help>
            <valueHelp>
              <format>u32</format>
              <description>Local preference</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-4294967295"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="deterministic-med">
      <properties>
        <help>Compare MEDs between different peers in the same AS</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="distance">
      <properties>
        <help>Administratives distances for BGP routes</help>
      </properties>
      <children>
        <node name="global">
          <properties>
            <help>Global administratives distances for BGP routes</help>
          </properties>
          <children>
            <leafNode name="external">
              <properties>
                <help>Administrative distance for external BGP routes</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>Administrative distance for external BGP routes</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="internal">
              <properties>
                <help>Administrative distance for internal BGP routes</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>Administrative distance for internal BGP routes</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="local">
              <properties>
                <help>Administrative distance for local BGP routes</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>Administrative distance for internal BGP routes</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
          </children>
        </node>
        <tagNode name="prefix">
          <properties>
            <help>Administrative distance for a specific BGP prefix</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>Administrative distance for a specific BGP prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
          <children>
            <leafNode name="distance">
              <properties>
                <help>Administrative distance for prefix</help>
                <valueHelp>
                  <format>u32:1-255</format>
                  <description>Administrative distance for external BGP routes</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 1-255"/>
                </constraint>
              </properties>
            </leafNode>
          </children>
        </tagNode>
      </children>
    </node>
    <leafNode name="ebgp-requires-policy">
      <properties>
        <help>Require in and out policy for eBGP peers (RFC8212)</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="fast-convergence">
      <properties>
        <help>Teardown sessions immediately whenever peer becomes unreachable</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="graceful-restart">
      <properties>
        <help>Graceful restart capability parameters</help>
      </properties>
      <children>
        <leafNode name="stalepath-time">
          <properties>
            <help>Maximum time to hold onto restarting neighbors stale paths</help>
            <valueHelp>
              <format>u32:1-3600</format>
              <description>Hold time in seconds</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-3600"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="graceful-shutdown">
      <properties>
        <help>Graceful shutdown</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="log-neighbor-changes">
      <properties>
        <help>Log neighbor up/down changes and reset reason</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="minimum-holdtime">
      <properties>
        <help>BGP minimum holdtime</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Minimum holdtime in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="network-import-check">
      <properties>
        <help>Enable IGP route check for network statements</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="no-client-to-client-reflection">
      <properties>
        <help>Disable client to client route reflection</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="no-fast-external-failover">
      <properties>
        <help>Disable immediate session reset on peer link down event</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="no-suppress-duplicates">
      <properties>
        <help>Disable suppress duplicate updates if the route actually not changed</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="reject-as-sets">
      <properties>
        <help>Reject routes with AS_SET or AS_CONFED_SET flag</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="shutdown">
      <properties>
        <help>Administrative shutdown of the BGP instance</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="suppress-fib-pending">
      <properties>
        <help>Advertise only routes that are programmed in kernel to peers</help>
        <valueless/>
      </properties>
    </leafNode>
    #include <include/router-id.xml.i>
  </children>
</node>
<tagNode name="peer-group">
  <properties>
    <help>Name of peer-group</help>
    <constraint>
      <regex>[-_a-zA-Z0-9]+</regex>
    </constraint>
  </properties>
  <children>
    <node name="address-family">
      <properties>
        <help>Address-family parameters</help>
      </properties>
      <children>
        #include <include/bgp/neighbor-afi-ipv4-unicast.xml.i>
        #include <include/bgp/neighbor-afi-ipv6-unicast.xml.i>
        #include <include/bgp/neighbor-afi-l2vpn-evpn.xml.i>
      </children>
    </node>
    #include <include/generic-description.xml.i>
    #include <include/bgp/neighbor-bfd.xml.i>
    #include <include/bgp/neighbor-capability.xml.i>
    #include <include/bgp/neighbor-disable-capability-negotiation.xml.i>
    #include <include/bgp/neighbor-disable-connected-check.xml.i>
    #include <include/bgp/neighbor-ebgp-multihop.xml.i>
    #include <include/bgp/neighbor-graceful-restart.xml.i>
    #include <include/bgp/neighbor-graceful-restart.xml.i>
    #include <include/bgp/neighbor-local-as.xml.i>
    #include <include/bgp/neighbor-override-capability.xml.i>
    #include <include/bgp/neighbor-passive.xml.i>
    #include <include/bgp/neighbor-password.xml.i>
    #include <include/bgp/remote-as.xml.i>
    #include <include/bgp/neighbor-shutdown.xml.i>
    #include <include/bgp/neighbor-ttl-security.xml.i>
    #include <include/bgp/neighbor-update-source.xml.i>
  </children>
</tagNode>
#include <include/route-map.xml.i>
<node name="timers">
  <properties>
    <help>BGP protocol timers</help>
  </properties>
  <children>
    #include <include/bgp/timers-holdtime.xml.i>
    #include <include/bgp/timers-keepalive.xml.i>
  </children>
</node>
<!-- include end -->
