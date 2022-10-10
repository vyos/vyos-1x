<!-- include start from policy/route-common-rule.xml.i -->
#include <include/policy/route-rule-action.xml.i>
#include <include/generic-description.xml.i>
<leafNode name="disable">
  <properties>
    <help>Option to disable firewall rule</help>
    <valueless/>
  </properties>
</leafNode>
<node name="fragment">
  <properties>
    <help>IP fragment match</help>
  </properties>
  <children>
    <leafNode name="match-frag">
      <properties>
        <help>Second and further fragments of fragmented packets</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="match-non-frag">
      <properties>
        <help>Head fragments or unfragmented packets</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<node name="ipsec">
  <properties>
    <help>Inbound IPsec packets</help>
  </properties>
  <children>
    <leafNode name="match-ipsec">
      <properties>
        <help>Inbound IPsec packets</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="match-none">
      <properties>
        <help>Inbound non-IPsec packets</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<node name="limit">
  <properties>
    <help>Rate limit using a token bucket filter</help>
  </properties>
  <children>
    <leafNode name="burst">
      <properties>
        <help>Maximum number of packets to allow in excess of rate</help>
        <valueHelp>
          <format>u32:0-4294967295</format>
          <description>Maximum number of packets to allow in excess of rate</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="rate">
      <properties>
        <help>Maximum average matching rate</help>
        <valueHelp>
          <format>u32:0-4294967295</format>
          <description>Maximum average matching rate</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<leafNode name="log">
  <properties>
    <help>Option to log packets matching rule</help>
    <completionHelp>
      <list>enable disable</list>
    </completionHelp>
    <valueHelp>
      <format>enable</format>
      <description>Enable log</description>
    </valueHelp>
    <valueHelp>
      <format>disable</format>
      <description>Disable log</description>
    </valueHelp>
    <constraint>
      <regex>(enable|disable)</regex>
    </constraint>
  </properties>
</leafNode>
<leafNode name="protocol">
  <properties>
    <help>Protocol to match (protocol name, number, or "all")</help>
    <completionHelp>
      <script>cat /etc/protocols | sed -e '/^#.*/d' | awk '{ print $1 }'</script>
    </completionHelp>
    <valueHelp>
      <format>all</format>
      <description>All IP protocols</description>
    </valueHelp>
    <valueHelp>
      <format>tcp_udp</format>
      <description>Both TCP and UDP</description>
    </valueHelp>
    <valueHelp>
      <format>0-255</format>
      <description>IP protocol number</description>
    </valueHelp>
    <valueHelp>
      <format>!&lt;protocol&gt;</format>
      <description>IP protocol number</description>
    </valueHelp>
    <constraint>
      <validator name="ip-protocol"/>
    </constraint>
  </properties>
  <defaultValue>all</defaultValue>
</leafNode>
<node name="recent">
  <properties>
    <help>Parameters for matching recently seen sources</help>
  </properties>
  <children>
    <leafNode name="count">
      <properties>
        <help>Source addresses seen more than N times</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Source addresses seen more than N times</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="time">
      <properties>
        <help>Source addresses seen in the last N seconds</help>
        <valueHelp>
          <format>u32:0-4294967295</format>
          <description>Source addresses seen in the last N seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<node name="set">
  <properties>
    <help>Packet modifications</help>
  </properties>
  <children>
    <leafNode name="dscp">
      <properties>
        <help>Packet Differentiated Services Codepoint (DSCP)</help>
        <valueHelp>
          <format>u32:0-63</format>
          <description>DSCP number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-63"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="mark">
      <properties>
        <help>Packet marking</help>
        <valueHelp>
          <format>u32:1-2147483647</format>
          <description>Packet marking</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-2147483647"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="table">
      <properties>
        <help>Routing table to forward packet with</help>
        <valueHelp>
          <format>u32:1-200</format>
          <description>Table number</description>
        </valueHelp>
        <valueHelp>
          <format>main</format>
          <description>Main table</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-200"/>
          <regex>(main)</regex>
        </constraint>
        <completionHelp>
          <list>main</list>
          <path>protocols static table</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="tcp-mss">
      <properties>
        <help>TCP Maximum Segment Size</help>
        <valueHelp>
          <format>u32:500-1460</format>
          <description>Explicitly set TCP MSS value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 500-1460"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<node name="source">
  <properties>
    <help>Source parameters</help>
  </properties>
  <children>
    #include <include/firewall/address-ipv6.xml.i>
    #include <include/firewall/source-destination-group.xml.i>
    <leafNode name="mac-address">
      <properties>
        <help>Source MAC address</help>
        <valueHelp>
          <format>&lt;MAC address&gt;</format>
          <description>MAC address to match</description>
        </valueHelp>
        <valueHelp>
          <format>!&lt;MAC address&gt;</format>
          <description>Match everything except the specified MAC address</description>
        </valueHelp>
        <constraint>
          <validator name="mac-address-firewall"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/firewall/port.xml.i>
  </children>
</node>
<node name="state">
  <properties>
    <help>Session state</help>
  </properties>
  <children>
    <leafNode name="established">
      <properties>
        <help>Established state</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="invalid">
      <properties>
        <help>Invalid state</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="new">
      <properties>
        <help>New state</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="related">
      <properties>
        <help>Related state</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
#include <include/firewall/tcp-flags.xml.i>
<node name="time">
  <properties>
    <help>Time to match rule</help>
  </properties>
  <children>
    <leafNode name="monthdays">
      <properties>
        <help>Monthdays to match rule on</help>
      </properties>
    </leafNode>
    <leafNode name="startdate">
      <properties>
        <help>Date to start matching rule</help>
      </properties>
    </leafNode>
    <leafNode name="starttime">
      <properties>
        <help>Time of day to start matching rule</help>
      </properties>
    </leafNode>
    <leafNode name="stopdate">
      <properties>
        <help>Date to stop matching rule</help>
      </properties>
    </leafNode>
    <leafNode name="stoptime">
      <properties>
        <help>Time of day to stop matching rule</help>
      </properties>
    </leafNode>
    <leafNode name="utc">
      <properties>
        <help>Interpret times for startdate, stopdate, starttime and stoptime to be UTC</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="weekdays">
      <properties>
        <help>Weekdays to match rule on</help>
      </properties>
    </leafNode>
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
