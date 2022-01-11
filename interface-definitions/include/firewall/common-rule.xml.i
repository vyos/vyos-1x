<!-- include start from firewall/common-rule.xml.i -->
#include <include/firewall/action.xml.i>
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
      <regex>^(enable|disable)$</regex>
    </constraint>
  </properties>
</leafNode>
<leafNode name="protocol">
  <properties>
    <help>Protocol to match (protocol name, number, or "all")</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_protocols.sh</script>
      <list>all tcp_udp</list>
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
      <format>u32:0-255</format>
      <description>IP protocol number</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;protocol&gt;</format>
      <description>IP protocol name</description>
    </valueHelp>
    <valueHelp>
      <format>!&lt;protocol&gt;</format>
      <description>IP protocol name</description>
    </valueHelp>
    <constraint>
      <validator name="ip-protocol"/>
    </constraint>
  </properties>
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
          <regex>^(enable|disable)$</regex>
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
          <regex>^(enable|disable)$</regex>
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
          <regex>^(enable|disable)$</regex>
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
          <regex>^(enable|disable)$</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<node name="tcp">
  <properties>
    <help>TCP flags to match</help>
  </properties>
  <children>
    <leafNode name="flags">
      <properties>
        <help>TCP flags to match</help>
        <valueHelp>
          <format>txt</format>
          <description>TCP flags to match</description>
        </valueHelp>
        <valueHelp>
          <format> </format>
          <description>\n\n  Allowed values for TCP flags : SYN ACK FIN RST URG PSH ALL\n  When specifying more than one flag, flags should be comma-separated.\n For example : value of 'SYN,!ACK,!FIN,!RST' will only match packets with\n  the SYN flag set, and the ACK, FIN and RST flags unset</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<node name="time">
  <properties>
    <help>Time to match rule</help>
  </properties>
  <children>
    <leafNode name="startdate">
      <properties>
        <help>Date to start matching rule</help>
        <valueHelp>
          <format>txt</format>
          <description>Enter date using following notation - YYYY-MM-DD</description>
        </valueHelp>
        <constraint>
          <regex>^(\d{4}\-\d{2}\-\d{2})$</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="starttime">
      <properties>
        <help>Time of day to start matching rule</help>
        <valueHelp>
          <format>txt</format>
          <description>Enter time using using 24 hour notation - hh:mm:ss</description>
        </valueHelp>
        <constraint>
          <regex>^([0-2][0-9](\:[0-5][0-9]){1,2})$</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="stopdate">
      <properties>
        <help>Date to stop matching rule</help>
        <valueHelp>
          <format>txt</format>
          <description>Enter date using following notation - YYYY-MM-DD</description>
        </valueHelp>
        <constraint>
          <regex>^(\d{4}\-\d{2}\-\d{2})$</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="stoptime">
      <properties>
        <help>Time of day to stop matching rule</help>
        <valueHelp>
          <format>txt</format>
          <description>Enter time using using 24 hour notation - hh:mm:ss</description>
        </valueHelp>
        <constraint>
          <regex>^([0-2][0-9](\:[0-5][0-9]){1,2})$</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="weekdays">
      <properties>
        <help>Comma separated weekdays to match rule on</help>
        <valueHelp>
          <format>txt</format>
          <description>Name of day (Monday, Tuesday, Wednesday, Thursdays, Friday, Saturday, Sunday)</description>
        </valueHelp>
        <valueHelp>
          <format>u32:0-6</format>
          <description>Day number (0 = Sunday ... 6 = Saturday)</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
