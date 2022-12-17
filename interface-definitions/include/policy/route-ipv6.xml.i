<!-- include start from policy/route-ipv6.xml.i -->
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address-ipv6.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
    #include <include/firewall/mac-address.xml.i>
    #include <include/firewall/port.xml.i>
  </children>
</node>
<node name="icmpv6">
  <properties>
    <help>ICMPv6 type and code information</help>
  </properties>
  <children>
    <leafNode name="type">
      <properties>
        <help>ICMP type-name</help>
        <completionHelp>
          <list>any echo-reply pong destination-unreachable network-unreachable host-unreachable protocol-unreachable port-unreachable fragmentation-needed source-route-failed network-unknown host-unknown network-prohibited host-prohibited TOS-network-unreachable TOS-host-unreachable communication-prohibited host-precedence-violation precedence-cutoff source-quench redirect network-redirect host-redirect TOS-network-redirect TOS host-redirect echo-request ping router-advertisement router-solicitation time-exceeded ttl-exceeded ttl-zero-during-transit ttl-zero-during-reassembly parameter-problem ip-header-bad required-option-missing timestamp-request timestamp-reply address-mask-request address-mask-reply packet-too-big</list>
        </completionHelp>
        <valueHelp>
          <format>any</format>
          <description>Any ICMP type/code</description>
        </valueHelp>
        <valueHelp>
          <format>echo-reply</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>pong</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>destination-unreachable</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>network-unreachable</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>host-unreachable</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>protocol-unreachable</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>port-unreachable</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>fragmentation-needed</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>source-route-failed</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>network-unknown</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>host-unknown</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>network-prohibited</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>host-prohibited</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>TOS-network-unreachable</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>TOS-host-unreachable</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>communication-prohibited</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>host-precedence-violation</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>precedence-cutoff</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>source-quench</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>redirect</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>network-redirect</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>host-redirect</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>TOS-network-redirect</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>TOS host-redirect</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>echo-request</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>ping</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>router-advertisement</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>router-solicitation</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>time-exceeded</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>ttl-exceeded</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>ttl-zero-during-transit</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>ttl-zero-during-reassembly</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>parameter-problem</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>ip-header-bad</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>required-option-missing</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>timestamp-request</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>timestamp-reply</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>address-mask-request</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>address-mask-reply</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <valueHelp>
          <format>packet-too-big</format>
          <description>ICMP type/code name</description>
        </valueHelp>
        <constraint>
          <regex>(any|echo-reply|pong|destination-unreachable|network-unreachable|host-unreachable|protocol-unreachable|port-unreachable|fragmentation-needed|source-route-failed|network-unknown|host-unknown|network-prohibited|host-prohibited|TOS-network-unreachable|TOS-host-unreachable|communication-prohibited|host-precedence-violation|precedence-cutoff|source-quench|redirect|network-redirect|host-redirect|TOS-network-redirect|TOS host-redirect|echo-request|ping|router-advertisement|router-solicitation|time-exceeded|ttl-exceeded|ttl-zero-during-transit|ttl-zero-during-reassembly|parameter-problem|ip-header-bad|required-option-missing|timestamp-request|timestamp-reply|address-mask-request|address-mask-reply|packet-too-big)</regex>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
