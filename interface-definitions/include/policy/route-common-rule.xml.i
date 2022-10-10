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
    #include <include/firewall/address.xml.i>
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
<node name="icmp">
  <properties>
    <help>ICMP type and code information</help>
  </properties>
  <children>
    <leafNode name="code">
      <properties>
        <help>ICMP code (0-255)</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMP code (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="type">
      <properties>
        <help>ICMP type (0-255)</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>ICMP type (0-255)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/firewall/icmp-type-name.xml.i>
  </children>
</node>
<!-- include end -->
