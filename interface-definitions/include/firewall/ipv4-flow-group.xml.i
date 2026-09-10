<!-- include start from firewall/ipv4-flow-group.xml.i -->
<tagNode name="ipv4-flow-group">
  <properties>
    <help>Firewall IPv4 flow-group (nftables concatenated set)</help>
    <constraint>
      #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
    </constraint>
    <constraintErrorMessage>Name of firewall group can only contain alphanumeric letters, hyphen, underscores and dot</constraintErrorMessage>
  </properties>
  <children>
    #include <include/generic-description.xml.i>
    <leafNode name="parameter">
      <properties>
        <help>Packet field included in the concatenated set key</help>
        <completionHelp>
          <list>inbound-interface outbound-interface ipv4-source-address ipv4-destination-address source-port destination-port protocol mark connection-mark dscp icmp-type icmp-code</list>
        </completionHelp>
        <valueHelp>
          <format>inbound-interface</format>
          <description>Inbound interface name</description>
        </valueHelp>
        <valueHelp>
          <format>outbound-interface</format>
          <description>Outbound interface name</description>
        </valueHelp>
        <valueHelp>
          <format>ipv4-source-address</format>
          <description>IPv4 source address</description>
        </valueHelp>
        <valueHelp>
          <format>ipv4-destination-address</format>
          <description>IPv4 destination address</description>
        </valueHelp>
        <valueHelp>
          <format>source-port</format>
          <description>Transport source port</description>
        </valueHelp>
        <valueHelp>
          <format>destination-port</format>
          <description>Transport destination port</description>
        </valueHelp>
        <valueHelp>
          <format>protocol</format>
          <description>IP protocol</description>
        </valueHelp>
        <valueHelp>
          <format>mark</format>
          <description>Packet mark</description>
        </valueHelp>
        <valueHelp>
          <format>connection-mark</format>
          <description>Connection mark</description>
        </valueHelp>
        <valueHelp>
          <format>dscp</format>
          <description>DSCP value</description>
        </valueHelp>
        <valueHelp>
          <format>icmp-type</format>
          <description>ICMP type</description>
        </valueHelp>
        <valueHelp>
          <format>icmp-code</format>
          <description>ICMP code</description>
        </valueHelp>
        <constraint>
          <regex>(inbound-interface|outbound-interface|ipv4-source-address|ipv4-destination-address|source-port|destination-port|protocol|mark|connection-mark|dscp|icmp-type|icmp-code)</regex>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <tagNode name="match">
      <properties>
        <help>Concatenated set element (identifier is informational only)</help>
        <constraint>
          #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
        </constraint>
        <constraintErrorMessage>Match name can only contain alphanumeric letters, hyphen, underscores and dot</constraintErrorMessage>
      </properties>
      <children>
        #include <include/generic-description.xml.i>
        #include <include/generic-disable-node.xml.i>
        <leafNode name="inbound-interface">
          <properties>
            <help>Inbound interface name</help>
            <completionHelp>
              <script>${vyos_completion_dir}/list_interfaces</script>
            </completionHelp>
            <valueHelp>
              <format>txt</format>
              <description>Interface name</description>
            </valueHelp>
            <constraint>
              #include <include/constraint/interface-name.xml.i>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="outbound-interface">
          <properties>
            <help>Outbound interface name</help>
            <completionHelp>
              <script>${vyos_completion_dir}/list_interfaces</script>
            </completionHelp>
            <valueHelp>
              <format>txt</format>
              <description>Interface name</description>
            </valueHelp>
            <constraint>
              #include <include/constraint/interface-name.xml.i>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="ipv4-source-address">
          <properties>
            <help>IPv4 source address</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IPv4 address to match</description>
            </valueHelp>
            <valueHelp>
              <format>ipv4net</format>
              <description>IPv4 prefix to match</description>
            </valueHelp>
            <valueHelp>
              <format>ipv4range</format>
              <description>IPv4 range to match (e.g. 10.0.0.1-10.0.0.200)</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-address"/>
              <validator name="ipv4-prefix"/>
              <validator name="ipv4-range"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="ipv4-destination-address">
          <properties>
            <help>IPv4 destination address</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IPv4 address to match</description>
            </valueHelp>
            <valueHelp>
              <format>ipv4net</format>
              <description>IPv4 prefix to match</description>
            </valueHelp>
            <valueHelp>
              <format>ipv4range</format>
              <description>IPv4 range to match (e.g. 10.0.0.1-10.0.0.200)</description>
            </valueHelp>
            <constraint>
              <validator name="ipv4-address"/>
              <validator name="ipv4-prefix"/>
              <validator name="ipv4-range"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="source-port">
          <properties>
            <help>Transport source port</help>
            <valueHelp>
              <format>txt</format>
              <description>Named port (any name in /etc/services, e.g., http)</description>
            </valueHelp>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Numbered port</description>
            </valueHelp>
            <valueHelp>
              <format>start-end</format>
              <description>Numbered port range (e.g. 1001-1050)</description>
            </valueHelp>
            <constraint>
              <validator name="port-range"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="destination-port">
          <properties>
            <help>Transport destination port</help>
            <valueHelp>
              <format>txt</format>
              <description>Named port (any name in /etc/services, e.g., http)</description>
            </valueHelp>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Numbered port</description>
            </valueHelp>
            <valueHelp>
              <format>start-end</format>
              <description>Numbered port range (e.g. 1001-1050)</description>
            </valueHelp>
            <constraint>
              <validator name="port-range"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="protocol">
          <properties>
            <help>IP protocol</help>
            <completionHelp>
              <script>${vyos_completion_dir}/list_protocols.sh</script>
            </completionHelp>
            <valueHelp>
              <format>u32:0-255</format>
              <description>IP protocol number</description>
            </valueHelp>
            <valueHelp>
              <format>&lt;protocol&gt;</format>
              <description>IP protocol name</description>
            </valueHelp>
            <constraint>
              <validator name="ip-protocol"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="mark">
          <properties>
            <help>Packet mark</help>
            <valueHelp>
              <format>u32:0-2147483647</format>
              <description>Firewall mark to match</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-2147483647"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="connection-mark">
          <properties>
            <help>Connection mark</help>
            <valueHelp>
              <format>u32:0-2147483647</format>
              <description>Connection mark to match</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-2147483647"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="dscp">
          <properties>
            <help>DSCP value</help>
            <valueHelp>
              <format>u32:0-63</format>
              <description>DSCP value to match</description>
            </valueHelp>
            <valueHelp>
              <format>&lt;start-end&gt;</format>
              <description>DSCP range to match</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--allow-range --range 0-63"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="icmp-type">
          <properties>
            <help>ICMP type</help>
            <completionHelp>
              <list>echo-reply destination-unreachable source-quench redirect echo-request router-advertisement router-solicitation time-exceeded parameter-problem timestamp-request timestamp-reply info-request info-reply address-mask-request address-mask-reply</list>
            </completionHelp>
            <valueHelp>
              <format>u32:0-255</format>
              <description>ICMP type number</description>
            </valueHelp>
            <valueHelp>
              <format>txt</format>
              <description>ICMP type name (e.g. echo-request)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-255"/>
              <regex>(echo-reply|destination-unreachable|source-quench|redirect|echo-request|router-advertisement|router-solicitation|time-exceeded|parameter-problem|timestamp-request|timestamp-reply|info-request|info-reply|address-mask-request|address-mask-reply)</regex>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="icmp-code">
          <properties>
            <help>ICMP code</help>
            <valueHelp>
              <format>u32:0-255</format>
              <description>ICMP code (must be valid for the selected icmp-type)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-255"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- include end -->
