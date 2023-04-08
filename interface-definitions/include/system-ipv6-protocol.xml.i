<!-- include start from system-ipv6-protocol.xml.i -->
<tagNode name="protocol">
  <properties>
    <help>Filter routing info exchanged between routing protocol and zebra</help>
    <completionHelp>
      <list>any babel bgp connected isis kernel ospfv3 ripng static table</list>
    </completionHelp>
    <valueHelp>
      <format>any</format>
      <description>Any of the above protocols</description>
    </valueHelp>
    <valueHelp>
      <format>babel</format>
      <description>Babel routing protocol</description>
    </valueHelp>
    <valueHelp>
      <format>bgp</format>
      <description>Border Gateway Protocol</description>
    </valueHelp>
    <valueHelp>
      <format>connected</format>
      <description>Connected routes (directly attached subnet or host)</description>
    </valueHelp>
    <valueHelp>
      <format>isis</format>
      <description>Intermediate System to Intermediate System</description>
    </valueHelp>
    <valueHelp>
      <format>kernel</format>
      <description>Kernel routes (not installed via the zebra RIB)</description>
    </valueHelp>
    <valueHelp>
      <format>ospfv3</format>
      <description>Open Shortest Path First (OSPFv3)</description>
    </valueHelp>
    <valueHelp>
      <format>ripng</format>
      <description>Routing Information Protocol next-generation</description>
    </valueHelp>
    <valueHelp>
      <format>static</format>
      <description>Statically configured routes</description>
    </valueHelp>
    <constraint>
      <regex>(any|babel|bgp|connected|isis|kernel|ospfv3|ripng|static|table)</regex>
    </constraint>
  </properties>
  <children>
    #include <include/route-map.xml.i>
  </children>
</tagNode>
<!-- include end -->
