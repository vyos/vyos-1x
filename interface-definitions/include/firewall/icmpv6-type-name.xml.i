<!-- include start from firewall/icmpv6-type-name.xml.i -->
<leafNode name="type-name">
  <properties>
    <help>ICMPv6 type-name</help>
    <completionHelp>
      <list>destination-unreachable packet-too-big time-exceeded echo-request echo-reply mld-listener-query mld-listener-report mld-listener-reduction nd-router-solicit nd-router-advert nd-neighbor-solicit nd-neighbor-advert nd-redirect parameter-problem router-renumbering ind-neighbor-solicit ind-neighbor-advert mld2-listener-report</list>
    </completionHelp>
    <valueHelp>
      <format>destination-unreachable</format>
      <description>ICMPv6 type 1: destination-unreachable</description>
    </valueHelp>
    <valueHelp>
      <format>packet-too-big</format>
      <description>ICMPv6 type 2: packet-too-big</description>
    </valueHelp>
    <valueHelp>
      <format>time-exceeded</format>
      <description>ICMPv6 type 3: time-exceeded</description>
    </valueHelp>
    <valueHelp>
      <format>echo-request</format>
      <description>ICMPv6 type 128: echo-request</description>
    </valueHelp>
    <valueHelp>
      <format>echo-reply</format>
      <description>ICMPv6 type 129: echo-reply</description>
    </valueHelp>
    <valueHelp>
      <format>mld-listener-query</format>
      <description>ICMPv6 type 130: mld-listener-query</description>
    </valueHelp>
    <valueHelp>
      <format>mld-listener-report</format>
      <description>ICMPv6 type 131: mld-listener-report</description>
    </valueHelp>
    <valueHelp>
      <format>mld-listener-reduction</format>
      <description>ICMPv6 type 132: mld-listener-reduction</description>
    </valueHelp>
    <valueHelp>
      <format>nd-router-solicit</format>
      <description>ICMPv6 type 133: nd-router-solicit</description>
    </valueHelp>
    <valueHelp>
      <format>nd-router-advert</format>
      <description>ICMPv6 type 134: nd-router-advert</description>
    </valueHelp>
    <valueHelp>
      <format>nd-neighbor-solicit</format>
      <description>ICMPv6 type 135: nd-neighbor-solicit</description>
    </valueHelp>
    <valueHelp>
      <format>nd-neighbor-advert</format>
      <description>ICMPv6 type 136: nd-neighbor-advert</description>
    </valueHelp>
    <valueHelp>
      <format>nd-redirect</format>
      <description>ICMPv6 type 137: nd-redirect</description>
    </valueHelp>
    <valueHelp>
      <format>parameter-problem</format>
      <description>ICMPv6 type 4: parameter-problem</description>
    </valueHelp>
    <valueHelp>
      <format>router-renumbering</format>
      <description>ICMPv6 type 138: router-renumbering</description>
    </valueHelp>
    <valueHelp>
      <format>ind-neighbor-solicit</format>
      <description>ICMPv6 type 141: ind-neighbor-solicit</description>
    </valueHelp>
    <valueHelp>
      <format>ind-neighbor-advert</format>
      <description>ICMPv6 type 142: ind-neighbor-advert</description>
    </valueHelp>
    <valueHelp>
      <format>mld2-listener-report</format>
      <description>ICMPv6 type 143: mld2-listener-report</description>
    </valueHelp>
    <constraint>
      <regex>(destination-unreachable|packet-too-big|time-exceeded|echo-request|echo-reply|mld-listener-query|mld-listener-report|mld-listener-reduction|nd-router-solicit|nd-router-advert|nd-neighbor-solicit|nd-neighbor-advert|nd-redirect|parameter-problem|router-renumbering|ind-neighbor-solicit|ind-neighbor-advert|mld2-listener-report)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
