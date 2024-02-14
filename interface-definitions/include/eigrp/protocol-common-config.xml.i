<!-- include start from eigrp/protocol-common-config.xml.i -->
<leafNode name="system-as">
  <properties>
    <help>Autonomous System Number (ASN)</help>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Autonomous System Number</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-65535"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="maximum-paths">
  <properties>
    <help>Forward packets over multiple paths</help>
    <valueHelp>
      <format>u32:1-32</format>
      <description>Number of paths</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-32"/>
    </constraint>
  </properties>
</leafNode>
<node name="metric">
  <properties>
    <help>Modify metrics and parameters for advertisement</help>
  </properties>
  <children>
    <leafNode name="weights">
      <properties>
        <help>Modify metric coefficients</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>K1</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<leafNode name="network">
  <properties>
    <help>Enable routing on an IP network</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>EIGRP network prefix</description>
    </valueHelp>
    <constraint>
      <validator name="ip-prefix"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<leafNode name="passive-interface">
  <properties>
    <help>Suppress routing updates on an interface</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <multi/>
  </properties>
</leafNode>
<leafNode name="redistribute">
  <properties>
    <help>Redistribute information from another routing protocol</help>
    <valueHelp>
      <format>bgp</format>
      <description>Border Gateway Protocol (BGP)</description>
    </valueHelp>
    <valueHelp>
      <format>connected</format>
      <description>Connected routes</description>
    </valueHelp>
    <valueHelp>
      <format>nhrp</format>
      <description>Next Hop Resolution Protocol (NHRP)</description>
    </valueHelp>
    <valueHelp>
      <format>ospf</format>
      <description>Open Shortest Path First (OSPFv2)</description>
    </valueHelp>
    <valueHelp>
      <format>rip</format>
      <description>Routing Information Protocol (RIP)</description>
    </valueHelp>
    <valueHelp>
      <format>babel</format>
      <description>Babel routing protocol (Babel)</description>
    </valueHelp>
    <valueHelp>
      <format>static</format>
      <description>Statically configured routes</description>
    </valueHelp>
    <valueHelp>
      <format>vnc</format>
      <description>Virtual Network Control (VNC)</description>
    </valueHelp>
    <completionHelp>
      <list>bgp connected nhrp ospf rip static vnc</list>
    </completionHelp>
    <constraint>
      <regex>(bgp|connected|nhrp|ospf|rip|babel|static|vnc)</regex>
    </constraint>
    <multi/>
  </properties>
</leafNode>
#include <include/router-id.xml.i>
<!-- FRR error: active time not implemented yet -->
<leafNode name="variance">
  <properties>
    <help>Control load balancing variance</help>
    <valueHelp>
      <format>u32:1-128</format>
      <description>Metric variance multiplier</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-128"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
