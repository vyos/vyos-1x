<!-- include start from policy/route-common.xml.i -->
#include <include/policy/route-rule-action.xml.i>
#include <include/generic-description.xml.i>
#include <include/firewall/firewall-mark.xml.i>
#include <include/generic-disable-node.xml.i>
#include <include/firewall/fragment.xml.i>
#include <include/firewall/match-ipsec.xml.i>
#include <include/firewall/limit.xml.i>
#include <include/firewall/log.xml.i>
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
#include <include/firewall/set-packet-modifications-conn-mark.xml.i>
#include <include/firewall/set-packet-modifications-dscp.xml.i>
#include <include/firewall/set-packet-modifications-mark.xml.i>
#include <include/firewall/set-packet-modifications-table-and-vrf.xml.i>
#include <include/firewall/set-packet-modifications-tcp-mss.xml.i>
#include <include/firewall/state.xml.i>
#include <include/firewall/tcp-flags.xml.i>
#include <include/firewall/tcp-mss.xml.i>
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
<!-- include end -->
