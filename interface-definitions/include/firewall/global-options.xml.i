<!-- include start from firewall/global-options.xml.i -->
<node name="global-options">
  <properties>
    <help>Global Options</help>
  </properties>
  <children>
    <leafNode name="all-ping">
      <properties>
        <help>Policy for handling of all IPv4 ICMP echo requests</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable processing of all IPv4 ICMP echo requests</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable processing of all IPv4 ICMP echo requests</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>enable</defaultValue>
    </leafNode>
    <leafNode name="broadcast-ping">
      <properties>
        <help>Policy for handling broadcast IPv4 ICMP echo and timestamp requests</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable processing of broadcast IPv4 ICMP echo/timestamp requests</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable processing of broadcast IPv4 ICMP echo/timestamp requests</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>disable</defaultValue>
    </leafNode>
    <leafNode name="config-trap">
      <properties>
        <help>SNMP trap generation on firewall configuration changes</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable sending SNMP trap on firewall configuration change</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable sending SNMP trap on firewall configuration change</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>disable</defaultValue>
    </leafNode>
    <leafNode name="ip-src-route">
      <properties>
        <help>Policy for handling IPv4 packets with source route option</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable processing of IPv4 packets with source route option</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable processing of IPv4 packets with source route option</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>disable</defaultValue>
    </leafNode>
    <leafNode name="log-martians">
      <properties>
        <help>Policy for logging IPv4 packets with invalid addresses</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable logging of IPv4 packets with invalid addresses</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable logging of Ipv4 packets with invalid addresses</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>enable</defaultValue>
    </leafNode>
    <leafNode name="receive-redirects">
      <properties>
        <help>Policy for handling received IPv4 ICMP redirect messages</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable processing of received IPv4 ICMP redirect messages</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable processing of received IPv4 ICMP redirect messages</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>disable</defaultValue>
    </leafNode>
    <leafNode name="resolver-cache">
      <properties>
        <help>Retains last successful value if domain resolution fails</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="resolver-interval">
      <properties>
        <help>Domain resolver update interval</help>
        <valueHelp>
          <format>u32:10-3600</format>
          <description>Interval (seconds)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 10-3600"/>
        </constraint>
      </properties>
      <defaultValue>300</defaultValue>
    </leafNode>
    <leafNode name="send-redirects">
      <properties>
        <help>Policy for sending IPv4 ICMP redirect messages</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable sending IPv4 ICMP redirect messages</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable sending IPv4 ICMP redirect messages</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>enable</defaultValue>
    </leafNode>
    <leafNode name="source-validation">
      <properties>
        <help>Policy for source validation by reversed path, as specified in RFC3704</help>
        <completionHelp>
          <list>strict loose disable</list>
        </completionHelp>
        <valueHelp>
          <format>strict</format>
          <description>Enable Strict Reverse Path Forwarding as defined in RFC3704</description>
        </valueHelp>
        <valueHelp>
          <format>loose</format>
          <description>Enable Loose Reverse Path Forwarding as defined in RFC3704</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>No source validation</description>
        </valueHelp>
        <constraint>
          <regex>(strict|loose|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>disable</defaultValue>
    </leafNode>
    <leafNode name="syn-cookies">
      <properties>
        <help>Policy for using TCP SYN cookies with IPv4</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable use of TCP SYN cookies with IPv4</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable use of TCP SYN cookies with IPv4</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>enable</defaultValue>
    </leafNode>
    <leafNode name="twa-hazards-protection">
      <properties>
        <help>RFC1337 TCP TIME-WAIT assasination hazards protection</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable RFC1337 TIME-WAIT hazards protection</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable RFC1337 TIME-WAIT hazards protection</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>disable</defaultValue>
    </leafNode>
    <leafNode name="ipv6-receive-redirects">
      <properties>
        <help>Policy for handling received ICMPv6 redirect messages</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable processing of received ICMPv6 redirect messages</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable processing of received ICMPv6 redirect messages</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>disable</defaultValue>
    </leafNode>
    <leafNode name="ipv6-src-route">
      <properties>
        <help>Policy for handling IPv6 packets with routing extension header</help>
        <completionHelp>
          <list>enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable processing of IPv6 packets with routing header type 2</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable processing of IPv6 packets with routing header</description>
        </valueHelp>
        <constraint>
          <regex>(enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>disable</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
