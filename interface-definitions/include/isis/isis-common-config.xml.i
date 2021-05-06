<!-- include start from isis/isis-common-config.xml.i -->
<node name="area-password">
  <properties>
    <help>Configure the authentication password for an area</help>
  </properties>
  <children>
    <leafNode name="plaintext-password">
      <properties>
        <help>Plain-text authentication type</help>
        <valueHelp>
          <format>txt</format>
          <description>Level-wide password</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="md5">
      <properties>
        <help>MD5 authentication type</help>
        <valueHelp>
          <format>txt</format>
          <description>Level-wide password</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<node name="default-information">
  <properties>
    <help>Control distribution of default information</help>
  </properties>
  <children>
    <node name="originate">
      <properties>
        <help>Distribute a default route</help>
      </properties>
      <children>
        <node name="ipv4">
          <properties>
            <help>Distribute default route for IPv4</help>
          </properties>
          <children>
            <leafNode name="level-1">
              <properties>
                <help>Distribute default route into level-1</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="level-2">
              <properties>
                <help>Distribute default route into level-2</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
        <node name="ipv6">
          <properties>
            <help>Distribute default route for IPv6</help>
          </properties>
          <children>
            <leafNode name="level-1">
              <properties>
                <help>Distribute default route into level-1</help>
                <completionHelp>
                  <list>always</list>
                </completionHelp>
                <valueHelp>
                  <format>always</format>
                  <description>Always advertise default route</description>
                </valueHelp>
              </properties>
            </leafNode>
            <leafNode name="level-2">
              <properties>
                <help>Distribute default route into level-2</help>
                <completionHelp>
                  <list>always</list>
                </completionHelp>
                <valueHelp>
                  <format>always</format>
                  <description>Always advertise default route</description>
                </valueHelp>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
  </children>
</node>
<node name="domain-password">
  <properties>
    <help>Set the authentication password for a routing domain</help>
  </properties>
  <children>
    <leafNode name="plaintext-password">
      <properties>
        <help>Plain-text authentication type</help>
        <valueHelp>
          <format>txt</format>
          <description>Level-wide password</description>
        </valueHelp>
      </properties>
    </leafNode>
<!--
    <leafNode name="md5">
      <properties>
        <help>MD5 authentication type</help>
        <valueHelp>
          <format>txt</format>
          <description>Level-wide password</description>
        </valueHelp>
      </properties>
    </leafNode>
-->
  </children>
</node>
<leafNode name="dynamic-hostname">
  <properties>
    <help>Dynamic hostname for IS-IS</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="level">
  <properties>
    <help>IS-IS level number</help>
    <completionHelp>
      <list>level-1 level-1-2 level-2</list>
    </completionHelp>
    <valueHelp>
      <format>level-1</format>
      <description>Act as a station router</description>
    </valueHelp>
    <valueHelp>
      <format>level-1-2</format>
      <description>Act as both a station and an area router</description>
    </valueHelp>
    <valueHelp>
      <format>level-2</format>
      <description>Act as an area router</description>
    </valueHelp>
    <constraint>
      <regex>^(level-1|level-1-2|level-2)$</regex>
    </constraint>
  </properties>
</leafNode>
<leafNode name="lsp-gen-interval">
  <properties>
    <help>Minimum interval between regenerating same LSP</help>
    <valueHelp>
      <format>u32:1-120</format>
      <description>Minimum interval in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-120"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="lsp-mtu">
  <properties>
    <help>Configure the maximum size of generated LSPs</help>
    <valueHelp>
      <format>u32:128-4352</format>
      <description>Maximum size of generated LSPs</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 128-4352"/>
    </constraint>
  </properties>
  <defaultValue>1497</defaultValue>
</leafNode>
<leafNode name="lsp-refresh-interval">
  <properties>
    <help>LSP refresh interval</help>
    <valueHelp>
      <format>u32:1-65235</format>
      <description>LSP refresh interval in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65235"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="max-lsp-lifetime">
  <properties>
    <help>Maximum LSP lifetime</help>
    <valueHelp>
      <format>u32:350-65535</format>
      <description>LSP lifetime in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="metric-style">
  <properties>
    <help>Use old-style (ISO 10589) or new-style packet formats</help>
    <completionHelp>
      <list>narrow transition wide</list>
    </completionHelp>
    <valueHelp>
      <format>narrow</format>
      <description>Use old style of TLVs with narrow metric</description>
    </valueHelp>
    <valueHelp>
      <format>transition</format>
      <description>Send and accept both styles of TLVs during transition</description>
    </valueHelp>
    <valueHelp>
      <format>wide</format>
      <description>Use new style of TLVs to carry wider metric</description>
    </valueHelp>
    <constraint>
      <regex>^(narrow|transition|wide)$</regex>
    </constraint>
  </properties>
</leafNode>
<leafNode name="net">
  <properties>
    <help>A Network Entity Title for this process (ISO only)</help>
    <valueHelp>
      <format>XX.XXXX. ... .XXX.XX</format>
      <description>Network entity title (NET)</description>
    </valueHelp>
    <constraint>
      <regex>[a-fA-F0-9]{2}(\.[a-fA-F0-9]{4}){3,9}\.[a-fA-F0-9]{2}</regex>
    </constraint>
  </properties>
</leafNode>
<leafNode name="purge-originator">
  <properties>
    <help>Use the RFC 6232 purge-originator</help>
    <valueless/>
  </properties>
</leafNode>
<node name="traffic-engineering">
  <properties>
    <help>Show IS-IS neighbor adjacencies</help>
  </properties>
  <children>
    <leafNode name="enable">
      <properties>
        <help>Enable MPLS traffic engineering extensions</help>
        <valueless/>
      </properties>
    </leafNode>
<!--
    <node name="inter-as">
      <properties>
        <help>MPLS traffic engineering inter-AS support</help>
      </properties>
      <children>
        <leafNode name="level-1">
          <properties>
            <help>Area native mode self originate inter-AS LSP with L1 only flooding scope</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="level-1-2">
          <properties>
            <help>Area native mode self originate inter-AS LSP with L1 and L2 flooding scope</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="level-2">
          <properties>
            <help>Area native mode self originate inter-AS LSP with L2 only flooding scope</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="inter-as">
      <properties>
        <help>MPLS traffic engineering inter-AS support</help>
        <valueless/>
      </properties>
    </leafNode>
-->
    <leafNode name="address">
      <properties>
        <help>MPLS traffic engineering router ID</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<node name="segment-routing">
  <properties>
    <help>Segment-Routing (SPRING) settings</help>
  </properties>
  <children>
    <leafNode name="enable">
      <properties>
        <help>Enable segment-routing functionality</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="global-block">
      <properties>
        <help>Global block label range</help>
      </properties>
      <children>
        <leafNode name="low-label-value">
          <properties>
            <help>The lower bound of the global block</help>
            <valueHelp>
              <format>u32:16-1048575</format>
              <description>MPLS label value</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 16-1048575"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="high-label-value">
          <properties>
            <help>The upper bound of the global block</help>
            <valueHelp>
              <format>u32:16-1048575</format>
              <description>MPLS label value</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 16-1048575"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
<!--
    <node name="local-block">
      <properties>
        <help>Local Block label range</help>
      </properties>
      <children>
        <leafNode name="low-label-value">
          <properties>
            <help>The lower bound of the local block</help>
            <valueHelp>
              <format>u32:16-1048575</format>
              <description>MPLS label value</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="  range 16-1048575"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="high-label-value">
          <properties>
            <help>The upper bound of the local block</help>
            <valueHelp>
              <format>u32:16-1048575</format>
              <description>MPLS label value</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="  range 16-1048575"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
-->
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
        <help>Static IPv4/IPv6 prefix segment/label mapping</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 prefix segment</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6net</format>
          <description>IPv6 prefix segment</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-prefix"/>
          <validator name="ipv6-prefix"/>
        </constraint>
      </properties>
      <children>
        <node name="absolute">
          <properties>
            <help>Specify the absolute value of prefix segment/label ID</help>
          </properties>
          <children>
            <leafNode name="value">
              <properties>
                <help>Specify the absolute value of prefix segment/label ID</help>
                <valueHelp>
                  <format>u32:16-1048575</format>
                    <description>The absolute segment/label ID value</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 16-1048575"/>
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
    <node name="ipv4">
      <properties>
        <help>Redistribute IPv4 routes</help>
      </properties>
      <children>
        <node name="bgp">
          <properties>
            <help>Border Gateway Protocol (BGP)</help>
          </properties>
          <children>
            #include <include/isis/isis-redistribute-ipv4.xml.i>
          </children>
        </node>
        <node name="connected">
          <properties>
            <help>Redistribute connected routes into IS-IS</help>
          </properties>
          <children>
            #include <include/isis/isis-redistribute-ipv4.xml.i>
          </children>
        </node>
        <node name="kernel">
          <properties>
            <help>Redistribute kernel routes into IS-IS</help>
          </properties>
          <children>
            #include <include/isis/isis-redistribute-ipv4.xml.i>
          </children>
        </node>
        <node name="ospf">
          <properties>
            <help>Redistribute OSPF routes into IS-IS</help>
          </properties>
          <children>
            #include <include/isis/isis-redistribute-ipv4.xml.i>
          </children>
        </node>
        <node name="rip">
          <properties>
            <help>Redistribute RIP routes into IS-IS</help>
          </properties>
          <children>
            #include <include/isis/isis-redistribute-ipv4.xml.i>
          </children>
        </node>
        <node name="static">
          <properties>
            <help>Redistribute static routes into IS-IS</help>
          </properties>
          <children>
            #include <include/isis/isis-redistribute-ipv4.xml.i>
          </children>
        </node>
      </children>
    </node>
  </children>
</node>
<leafNode name="set-attached-bit">
  <properties>
    <help>Set attached bit to identify as L1/L2 router for inter-area traffic</help>
    <valueless/>
  </properties>
</leafNode>
<leafNode name="set-overload-bit">
  <properties>
    <help>Set overload bit to avoid any transit traffic</help>
    <valueless/>
  </properties>
</leafNode>
<node name="spf-delay-ietf">
  <properties>
    <help>IETF SPF delay algorithm</help>
  </properties>
  <children>
    <leafNode name="init-delay">
      <properties>
        <help>Delay used while in QUIET state</help>
        <valueHelp>
          <format>u32:0-60000</format>
          <description>Delay used while in QUIET state (in ms)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-60000"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="short-delay">
      <properties>
        <help>Delay used while in SHORT_WAIT state</help>
        <valueHelp>
          <format>u32:0-60000</format>
          <description>Delay used while in SHORT_WAIT state (in ms)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-60000"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="long-delay">
      <properties>
        <help>Delay used while in LONG_WAIT</help>
        <valueHelp>
          <format>u32:0-60000</format>
          <description>Delay used while in LONG_WAIT state (in ms)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-60000"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="holddown">
      <properties>
        <help>Time with no received IGP events before considering IGP stable</help>
        <valueHelp>
          <format>u32:0-60000</format>
          <description>Time with no received IGP events before considering IGP stable (in ms)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-60000"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="time-to-learn">
      <properties>
        <help>Maximum duration needed to learn all the events related to a single failure</help>
        <valueHelp>
          <format>u32:0-60000</format>
          <description>Maximum duration needed to learn all the events related to a single failure (in ms)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-60000"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<leafNode name="spf-interval">
  <properties>
    <help>Minimum interval between SPF calculations</help>
    <valueHelp>
      <format>u32:1-120</format>
      <description>Minimum interval between consecutive SPFs in seconds</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-120"/>
    </constraint>
  </properties>
</leafNode>
<tagNode name="interface">
  <!-- (config-if)# ip router isis WORD (same as name of IS-IS process)
        if any section of "interface" pesent  -->
  <properties>
    <help>Interface params</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces.py</script>
    </completionHelp>
  </properties>
  <children>
    #include <include/bfd.xml.i>
    <leafNode name="circuit-type">
      <properties>
        <help>Configure circuit type for interface</help>
        <completionHelp>
          <list>level-1 level-1-2 level-2-only</list>
        </completionHelp>
        <valueHelp>
          <format>level-1</format>
          <description>Level-1 only adjacencies are formed</description>
        </valueHelp>
        <valueHelp>
          <format>level-1-2</format>
          <description>Level-1-2 adjacencies are formed</description>
        </valueHelp>
        <valueHelp>
          <format>level-2-only</format>
          <description>Level-2 only adjacencies are formed</description>
        </valueHelp>
        <constraint>
          <regex>^(level-1|level-1-2|level-2-only)$</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="hello-padding">
      <properties>
        <help>Add padding to IS-IS hello packets</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="hello-interval">
      <properties>
        <help>Set Hello interval</help>
        <valueHelp>
          <format>u32:1-600</format>
          <description>Set Hello interval</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-600"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="hello-multiplier">
      <properties>
        <help>Set Hello interval</help>
        <valueHelp>
          <format>u32:2-100</format>
          <description>Set multiplier for Hello holding time</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 2-100"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="metric">
      <properties>
        <help>Set default metric for circuit</help>
        <valueHelp>
          <format>u32:0-16777215</format>
          <description>Default metric value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-16777215"/>
        </constraint>
      </properties>
    </leafNode>
    <node name="network">
      <properties>
        <help>Set network type</help>
      </properties>
      <children>
        <leafNode name="point-to-point">
          <properties>
            <help>point-to-point network type</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
    #include <include/isis/passive.xml.i>
    <node name="password">
      <properties>
        <help>Configure the authentication password for a circuit</help>
      </properties>
      <children>
        <leafNode name="plaintext-password">
          <properties>
            <help>Plain-text authentication type</help>
            <valueHelp>
              <format>txt</format>
              <description>Circuit password</description>
            </valueHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <leafNode name="priority">
      <properties>
        <help>Set priority for Designated Router election</help>
        <valueHelp>
          <format>u32:0-127</format>
          <description>Priority value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-127"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="psnp-interval">
      <properties>
        <help>Set PSNP interval in seconds</help>
        <valueHelp>
          <format>u32:0-127</format>
          <description>Priority value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-127"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="no-three-way-handshake">
      <properties>
        <help>Disable three-way handshake</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
