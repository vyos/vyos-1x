<!-- include start from ospf/protocol-common-config.xml.i -->
<node name="aggregation">
  <properties>
    <help>External route aggregation</help>
  </properties>
  <children>
    <leafNode name="timer">
      <properties>
        <help>Delay timer</help>
        <valueHelp>
          <format>u32:5-1800</format>
          <description>Timer interval in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 5-1800"/>
        </constraint>
      </properties>
      <defaultValue>5</defaultValue>
    </leafNode>
  </children>
</node>
<tagNode name="access-list">
  <properties>
    <help>Access list to filter networks in routing updates</help>
    <completionHelp>
      <path>policy access-list</path>
    </completionHelp>
    <valueHelp>
      <format>u32</format>
      <description>Access-list number</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967295"/>
    </constraint>
  </properties>
  <children>
    <leafNode name="export">
      <properties>
        <help>Filter for outgoing routing update</help>
        <completionHelp>
          <list>bgp connected kernel rip static</list>
        </completionHelp>
        <valueHelp>
          <format>bgp</format>
          <description>Filter BGP routes</description>
        </valueHelp>
        <valueHelp>
          <format>connected</format>
          <description>Filter connected routes</description>
        </valueHelp>
        <valueHelp>
          <format>isis</format>
          <description>Filter IS-IS routes</description>
        </valueHelp>
        <valueHelp>
          <format>kernel</format>
          <description>Filter Kernel routes</description>
        </valueHelp>
        <valueHelp>
          <format>rip</format>
          <description>Filter RIP routes</description>
        </valueHelp>
        <valueHelp>
          <format>static</format>
          <description>Filter static routes</description>
        </valueHelp>
        <constraint>
          <regex>(bgp|connected|isis|kernel|rip|static)</regex>
        </constraint>
        <constraintErrorMessage>Must be bgp, connected, kernel, rip, or static</constraintErrorMessage>
        <multi/>
      </properties>
    </leafNode>
  </children>
</tagNode>
<tagNode name="area">
  <properties>
    <help>OSPF area settings</help>
    <valueHelp>
      <format>u32</format>
      <description>OSPF area number in decimal notation</description>
    </valueHelp>
    <valueHelp>
      <format>ipv4</format>
      <description>OSPF area number in dotted decimal notation</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-4294967295"/>
      <validator name="ip-address"/>
    </constraint>
  </properties>
  <children>
    <node name="area-type">
      <properties>
        <help>Area type</help>
      </properties>
      <children>
        <leafNode name="normal">
          <properties>
            <help>Normal OSPF area</help>
            <valueless/>
          </properties>
        </leafNode>
        <node name="nssa">
          <properties>
            <help>Not-So-Stubby OSPF area</help>
          </properties>
          <children>
            <leafNode name="default-cost">
              <properties>
                <help>Summary-default cost of an NSSA area</help>
                <valueHelp>
                  <format>u32:0-16777215</format>
                  <description>Summary default cost</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 0-16777215"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="no-summary">
              <properties>
                <help>Do not inject inter-area routes into stub</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="translate">
              <properties>
                <help>Configure NSSA-ABR</help>
                <completionHelp>
                  <list>always candidate never</list>
                </completionHelp>
                <valueHelp>
                  <format>always</format>
                  <description>Always translate LSA types</description>
                </valueHelp>
                <valueHelp>
                  <format>candidate</format>
                  <description>Translate for election</description>
                </valueHelp>
                <valueHelp>
                  <format>never</format>
                  <description>Never translate LSA types</description>
                </valueHelp>
                <constraint>
                  <regex>(always|candidate|never)</regex>
                </constraint>
              </properties>
              <defaultValue>candidate</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="stub">
          <properties>
            <help>Stub OSPF area</help>
          </properties>
          <children>
            <leafNode name="default-cost">
              <properties>
                <help>Summary-default cost</help>
                <valueHelp>
                  <format>u32:0-16777215</format>
                  <description>Summary default cost</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 0-16777215"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="no-summary">
              <properties>
                <help>Do not inject inter-area routes into the stub</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
    <leafNode name="authentication">
      <properties>
        <help>OSPF area authentication type</help>
        <completionHelp>
          <list>plaintext-password md5</list>
        </completionHelp>
        <valueHelp>
          <format>plaintext-password</format>
          <description>Use plain-text authentication</description>
        </valueHelp>
        <valueHelp>
          <format>md5</format>
          <description>Use MD5 authentication</description>
        </valueHelp>
        <constraint>
          <regex>(plaintext-password|md5)</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="network">
      <properties>
        <help>OSPF network</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>OSPF network</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-prefix"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <tagNode name="range">
      <properties>
        <help>Summarize routes matching a prefix (border routers only)</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>Area range prefix</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-prefix"/>
        </constraint>
      </properties>
      <children>
        <leafNode name="cost">
          <properties>
            <help>Metric for this range</help>
            <valueHelp>
              <format>u32:0-16777215</format>
              <description>Metric for this range</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-16777215"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="not-advertise">
          <properties>
            <help>Do not advertise this range</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="substitute">
          <properties>
            <help>Advertise area range as another prefix</help>
            <valueHelp>
              <format>ipv4net</format>
              <description>Advertise area range as another prefix</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-prefix"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </tagNode>
    <leafNode name="shortcut">
      <properties>
        <help>Area shortcut mode</help>
        <completionHelp>
          <list>default disable enable</list>
        </completionHelp>
        <valueHelp>
          <format>default</format>
          <description>Set default</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable shortcutting mode</description>
        </valueHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable shortcutting mode</description>
        </valueHelp>
        <constraint>
          <regex>(default|disable|enable)</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="export-list">
      <properties>
        <help>Set the filter for networks announced to other areas</help>
        <completionHelp>
          <path>policy access-list</path>
        </completionHelp>
        <valueHelp>
          <format>u32</format>
          <description>Access-list number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="import-list">
      <properties>
        <help>Set the filter for networks from other areas announced</help>
        <completionHelp>
          <path>policy access-list</path>
        </completionHelp>
        <valueHelp>
          <format>u32</format>
          <description>Access-list number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
    <tagNode name="virtual-link">
      <properties>
        <help>Virtual link</help>
        <valueHelp>
          <format>ipv4</format>
          <description>OSPF area in dotted decimal notation</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
          <validator name="ip-address"/>
        </constraint>
      </properties>
      <children>
        #include <include/ospf/authentication.xml.i>
        #include <include/ospf/intervals.xml.i>
      </children>
    </tagNode>
  </children>
</tagNode>
#include <include/ospf/auto-cost.xml.i>
<node name="capability">
  <properties>
    <help>Enable specific OSPF features</help>
  </properties>
  <children>
    <leafNode name="opaque">
      <properties>
        <help>Opaque LSA</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
#include <include/ospf/default-information.xml.i>
<leafNode name="default-metric">
  <properties>
    <help>Metric of redistributed routes</help>
    <valueHelp>
      <format>u32:0-16777214</format>
      <description>Metric of redistributed routes</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-16777214"/>
    </constraint>
  </properties>
</leafNode>
#include <include/ospf/graceful-restart.xml.i>
<node name="graceful-restart">
  <children>
    <node name="helper">
      <children>
        <leafNode name="no-strict-lsa-checking">
          <properties>
            <help>Disable strict LSA check</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<leafNode name="maximum-paths">
  <properties>
    <help>Maximum multiple paths (ECMP)</help>
    <valueHelp>
      <format>u32:1-64</format>
      <description>Maximum multiple paths (ECMP)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-64"/>
    </constraint>
  </properties>
</leafNode>
#include <include/isis/ldp-sync-protocol.xml.i>
<node name="distance">
  <properties>
    <help>Administrative distance</help>
  </properties>
  <children>
    #include <include/ospf/distance-global.xml.i>
    <node name="ospf">
      <properties>
        <help>OSPF administrative distance</help>
      </properties>
      <children>
        #include <include/ospf/distance-per-protocol.xml.i>
      </children>
    </node>
  </children>
</node>
<tagNode name="interface">
  <properties>
    <help>Interface configuration</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
  </properties>
  <children>
    <leafNode name="area">
      <properties>
        <help>Enable OSPF on this interface</help>
        <completionHelp>
          <path>protocols ospf area</path>
        </completionHelp>
        <valueHelp>
          <format>u32</format>
          <description>OSPF area ID as decimal notation</description>
        </valueHelp>
        <valueHelp>
          <format>ipv4</format>
          <description>OSPF area ID in IP address notation</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
          <validator name="ip-address"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/ospf/authentication.xml.i>
    #include <include/ospf/intervals.xml.i>
    #include <include/ospf/interface-common.xml.i>
    #include <include/isis/ldp-sync-interface.xml.i>
    <leafNode name="bandwidth">
      <properties>
        <help>Interface bandwidth (Mbit/s)</help>
        <valueHelp>
          <format>u32:1-100000</format>
          <description>Bandwidth in Megabit/sec (for calculating OSPF cost)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-100000"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="hello-multiplier">
      <properties>
        <help>Hello multiplier factor</help>
        <valueHelp>
          <format>u32:1-10</format>
          <description>Number of Hellos to send each second</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-10"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="network">
      <properties>
        <help>Network type</help>
        <completionHelp>
          <list>broadcast non-broadcast point-to-multipoint point-to-point</list>
        </completionHelp>
        <valueHelp>
          <format>broadcast</format>
          <description>Broadcast network type</description>
        </valueHelp>
        <valueHelp>
          <format>non-broadcast</format>
          <description>Non-broadcast network type</description>
        </valueHelp>
        <valueHelp>
          <format>point-to-multipoint</format>
          <description>Point-to-multipoint network type</description>
        </valueHelp>
        <valueHelp>
          <format>point-to-point</format>
          <description>Point-to-point network type</description>
        </valueHelp>
        <constraint>
          <regex>(broadcast|non-broadcast|point-to-multipoint|point-to-point)</regex>
        </constraint>
        <constraintErrorMessage>Must be broadcast, non-broadcast, point-to-multipoint or point-to-point</constraintErrorMessage>
      </properties>
    </leafNode>
    <node name="passive">
      <properties>
        <help>Suppress routing updates on an interface</help>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
      </children>
    </node>
  </children>
</tagNode>
#include <include/ospf/log-adjacency-changes.xml.i>
<node name="max-metric">
  <properties>
    <help>OSPF maximum and infinite-distance metric</help>
  </properties>
  <children>
    <node name="router-lsa">
      <properties>
        <help>Advertise own Router-LSA with infinite distance (stub router)</help>
      </properties>
      <children>
        <leafNode name="administrative">
          <properties>
            <help>Administratively apply, for an indefinite period</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="on-shutdown">
          <properties>
            <help>Advertise stub-router prior to full shutdown of OSPF</help>
            <valueHelp>
              <format>u32:5-100</format>
              <description>Time (seconds) to advertise self as stub-router</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 5-100"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="on-startup">
          <properties>
            <help>Automatically advertise stub Router-LSA on startup of OSPF</help>
            <valueHelp>
              <format>u32:5-86400</format>
              <description>Time (seconds) to advertise self as stub-router</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 5-86400"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<node name="mpls-te">
  <properties>
    <help>MultiProtocol Label Switching-Traffic Engineering (MPLS-TE) parameters</help>
  </properties>
  <children>
    <leafNode name="enable">
      <properties>
        <help>Enable MPLS-TE functionality</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="router-address">
      <properties>
        <help>Stable IP address of the advertising router</help>
        <valueHelp>
          <format>ipv4</format>
          <description>Stable IP address of the advertising router</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
      <defaultValue>0.0.0.0</defaultValue>
    </leafNode>
  </children>
</node>
<tagNode name="neighbor">
  <properties>
    <help>Specify neighbor router</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Neighbor IP address</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
  <children>
    <leafNode name="poll-interval">
      <properties>
        <help>Dead neighbor polling interval</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Seconds between dead neighbor polling interval</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
      <defaultValue>60</defaultValue>
    </leafNode>
    <leafNode name="priority">
      <properties>
        <help>Neighbor priority in seconds</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>Neighbor priority</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
  </children>
</tagNode>
<node name="parameters">
  <properties>
    <help>OSPF specific parameters</help>
  </properties>
  <children>
    <leafNode name="abr-type">
      <properties>
        <help>OSPF ABR type</help>
        <completionHelp>
          <list>cisco ibm shortcut standard</list>
        </completionHelp>
        <valueHelp>
          <format>cisco</format>
          <description>Cisco ABR type</description>
        </valueHelp>
        <valueHelp>
          <format>ibm</format>
          <description>IBM ABR type</description>
        </valueHelp>
        <valueHelp>
          <format>shortcut</format>
          <description>Shortcut ABR type</description>
        </valueHelp>
        <valueHelp>
          <format>standard</format>
          <description>Standard ABR type</description>
        </valueHelp>
        <constraint>
          <regex>(cisco|ibm|shortcut|standard)</regex>
        </constraint>
      </properties>
      <defaultValue>cisco</defaultValue>
    </leafNode>
    <leafNode name="opaque-lsa">
      <properties>
        <help>Enable the Opaque-LSA capability (rfc2370)</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="rfc1583-compatibility">
      <properties>
        <help>Enable RFC1583 criteria for handling AS external routes</help>
        <valueless/>
      </properties>
    </leafNode>
    #include <include/router-id.xml.i>
  </children>
</node>
<leafNode name="passive-interface">
  <properties>
    <help>Suppress routing updates on an interface</help>
    <completionHelp>
      <list>default</list>
    </completionHelp>
    <valueHelp>
      <format>default</format>
      <description>Default to suppress routing updates on all interfaces</description>
    </valueHelp>
    <constraint>
      <regex>(default)</regex>
    </constraint>
  </properties>
</leafNode>
<node name="segment-routing">
  <properties>
    <help>Segment-Routing (SPRING) settings</help>
  </properties>
  <children>
    <node name="global-block">
      <properties>
        <help>Segment Routing Global Block label range</help>
      </properties>
      <children>
        #include <include/segment-routing-label-value.xml.i>
      </children>
    </node>
    <node name="local-block">
      <properties>
        <help>Segment Routing Local Block label range</help>
      </properties>
      <children>
        #include <include/segment-routing-label-value.xml.i>
      </children>
    </node>
    <leafNode name="maximum-label-depth">
      <properties>
        <help>Maximum MPLS labels allowed for this router</help>
        <valueHelp>
          <format>u32:1-16</format>
            <description>MPLS label depth</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-16"/>
        </constraint>
      </properties>
    </leafNode>
    <tagNode name="prefix">
      <properties>
        <help>Static IPv4 prefix segment/label mapping</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 prefix segment</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-prefix"/>
        </constraint>
      </properties>
      <children>
        <node name="index">
          <properties>
            <help>Specify the index value of prefix segment/label ID</help>
          </properties>
          <children>
            <leafNode name="value">
              <properties>
                <help>Specify the index value of prefix segment/label ID</help>
                <valueHelp>
                  <format>u32:0-65535</format>
                    <description>The index segment/label ID value</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 0-65535"/>
                </constraint>
              </properties>
            </leafNode>
            <leafNode name="explicit-null">
              <properties>
                <help>Request upstream neighbor to replace segment/label with explicit null label</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="no-php-flag">
              <properties>
                <help>Do not request penultimate hop popping for segment/label</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </tagNode>
  </children>
</node>
<node name="redistribute">
  <properties>
    <help>Redistribute information from another routing protocol</help>
  </properties>
  <children>
    <node name="bgp">
      <properties>
        <help>Redistribute BGP routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="connected">
      <properties>
        <help>Redistribute connected routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="isis">
      <properties>
        <help>Redistribute IS-IS routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="kernel">
      <properties>
        <help>Redistribute Kernel routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="rip">
      <properties>
        <help>Redistribute RIP routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="babel">
      <properties>
        <help>Redistribute Babel routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <node name="static">
      <properties>
        <help>Redistribute statically configured routes</help>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </node>
    <tagNode name="table">
      <properties>
        <help>Redistribute non-main Kernel Routing Table</help>
        <completionHelp>
          <path>protocols static table</path>
        </completionHelp>
        <valueHelp>
          <format>u32:1-200</format>
          <description>Policy route table number</description>
        </valueHelp>
      </properties>
      <children>
        #include <include/ospf/metric.xml.i>
        #include <include/ospf/metric-type.xml.i>
        #include <include/route-map.xml.i>
      </children>
    </tagNode>
  </children>
</node>
<node name="refresh">
  <properties>
    <help>Adjust refresh parameters</help>
  </properties>
  <children>
    <leafNode name="timers">
      <properties>
        <help>Refresh timer</help>
        <valueHelp>
          <format>u32:10-1800</format>
          <description>Timer value in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 10-1800"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<tagNode name="summary-address">
  <properties>
    <help>External summary address</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>OSPF area number in dotted decimal notation</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-prefix"/>
    </constraint>
  </properties>
  <children>
    <leafNode name="no-advertise">
      <properties>
        <help>Don not advertise summary route</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="tag">
      <properties>
        <help>Router tag</help>
        <valueHelp>
          <format>u32:1-4294967295</format>
          <description>Router tag value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</tagNode>
<node name="timers">
  <properties>
    <help>Adjust routing timers</help>
  </properties>
  <children>
    <node name="throttle">
      <properties>
        <help>Throttling adaptive timers</help>
      </properties>
      <children>
        <node name="spf">
          <properties>
            <help>OSPF SPF timers</help>
          </properties>
          <children>
            <leafNode name="delay">
              <properties>
                <help>Delay from the first change received to SPF calculation</help>
                <valueHelp>
                  <format>u32:0-600000</format>
                  <description>Delay in milliseconds</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 0-600000"/>
                </constraint>
              </properties>
              <defaultValue>200</defaultValue>
            </leafNode>
            <leafNode name="initial-holdtime">
              <properties>
                <help>Initial hold time between consecutive SPF calculations</help>
                <valueHelp>
                  <format>u32:0-600000</format>
                  <description>Initial hold time in milliseconds</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 0-600000"/>
                </constraint>
              </properties>
              <defaultValue>1000</defaultValue>
            </leafNode>
            <leafNode name="max-holdtime">
              <properties>
                <help>Maximum hold time</help>
                <valueHelp>
                  <format>u32:0-600000</format>
                  <description>Max hold time in milliseconds</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 0-600000"/>
                </constraint>
              </properties>
              <defaultValue>10000</defaultValue>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
