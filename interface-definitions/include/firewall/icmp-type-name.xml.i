<!-- include start from firewall/icmp-type-name.xml.i -->
<leafNode name="type-name">
  <properties>
    <help>ICMP type-name</help>
    <completionHelp>
      <list>echo-reply destination-unreachable source-quench redirect echo-request router-advertisement router-solicitation time-exceeded parameter-problem timestamp-request timestamp-reply info-request info-reply address-mask-request address-mask-reply</list>
    </completionHelp>
    <valueHelp>
      <format>echo-reply</format>
      <description>ICMP type 0: echo-reply</description>
    </valueHelp>
    <valueHelp>
      <format>destination-unreachable</format>
      <description>ICMP type 3: destination-unreachable</description>
    </valueHelp>
    <valueHelp>
      <format>source-quench</format>
      <description>ICMP type 4: source-quench</description>
    </valueHelp>
    <valueHelp>
      <format>redirect</format>
      <description>ICMP type 5: redirect</description>
    </valueHelp>
    <valueHelp>
      <format>echo-request</format>
      <description>ICMP type 8: echo-request</description>
    </valueHelp>
    <valueHelp>
      <format>router-advertisement</format>
      <description>ICMP type 9: router-advertisement</description>
    </valueHelp>
    <valueHelp>
      <format>router-solicitation</format>
      <description>ICMP type 10: router-solicitation</description>
    </valueHelp>
    <valueHelp>
      <format>time-exceeded</format>
      <description>ICMP type 11: time-exceeded</description>
    </valueHelp>
    <valueHelp>
      <format>parameter-problem</format>
      <description>ICMP type 12: parameter-problem</description>
    </valueHelp>
    <valueHelp>
      <format>timestamp-request</format>
      <description>ICMP type 13: timestamp-request</description>
    </valueHelp>
    <valueHelp>
      <format>timestamp-reply</format>
      <description>ICMP type 14: timestamp-reply</description>
    </valueHelp>
    <valueHelp>
      <format>info-request</format>
      <description>ICMP type 15: info-request</description>
    </valueHelp>
    <valueHelp>
      <format>info-reply</format>
      <description>ICMP type 16: info-reply</description>
    </valueHelp>
    <valueHelp>
      <format>address-mask-request</format>
      <description>ICMP type 17: address-mask-request</description>
    </valueHelp>
    <valueHelp>
      <format>address-mask-reply</format>
      <description>ICMP type 18: address-mask-reply</description>
    </valueHelp>
    <constraint>
      <regex>(echo-reply|destination-unreachable|source-quench|redirect|echo-request|router-advertisement|router-solicitation|time-exceeded|parameter-problem|timestamp-request|timestamp-reply|info-request|info-reply|address-mask-request|address-mask-reply)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
