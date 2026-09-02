<!-- include start from firewall/ipv6-flow-group.xml.i -->
<tagNode name="ipv6-flow-group">
  <properties>
    <help>Firewall IPv6 flow-group (nftables concatenated set)</help>
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
          <list>inbound-interface outbound-interface ipv6-source-address ipv6-destination-address source-port destination-port protocol mark connection-mark dscp icmpv6-type icmpv6-code</list>
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
          <format>ipv6-source-address</format>
          <description>IPv6 source address</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6-destination-address</format>
          <description>IPv6 destination address</description>
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
          <format>icmpv6-type</format>
          <description>ICMPv6 type</description>
        </valueHelp>
        <valueHelp>
          <format>icmpv6-code</format>
          <description>ICMPv6 code</description>
        </valueHelp>
        <constraint>
          <regex>(inbound-interface|outbound-interface|ipv6-source-address|ipv6-destination-address|source-port|destination-port|protocol|mark|connection-mark|dscp|icmpv6-type|icmpv6-code)</regex>
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
        <leafNode name="ipv6-source-address">
          <properties>
            <help>IPv6 source address</help>
            <valueHelp>
              <format>ipv6</format>
              <description>IPv6 address to match</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6net</format>
              <description>IPv6 prefix to match</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6range</format>
              <description>IPv6 range to match (e.g. 2002::1-2002::ff)</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-address"/>
              <validator name="ipv6-prefix"/>
              <validator name="ipv6-range"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="ipv6-destination-address">
          <properties>
            <help>IPv6 destination address</help>
            <valueHelp>
              <format>ipv6</format>
              <description>IPv6 address to match</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6net</format>
              <description>IPv6 prefix to match</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6range</format>
              <description>IPv6 range to match (e.g. 2002::1-2002::ff)</description>
            </valueHelp>
            <constraint>
              <validator name="ipv6-address"/>
              <validator name="ipv6-prefix"/>
              <validator name="ipv6-range"/>
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
        <leafNode name="icmpv6-type">
          <properties>
            <help>ICMPv6 type</help>
            <completionHelp>
              <list>destination-unreachable packet-too-big time-exceeded parameter-problem echo-request echo-reply mld-listener-query mld-listener-report mld-listener-done mld-listener-reduction nd-router-solicit nd-router-advert nd-neighbor-solicit nd-neighbor-advert nd-redirect router-renumbering ind-neighbor-solicit ind-neighbor-advert mld2-listener-report</list>
            </completionHelp>
            <valueHelp>
              <format>u32:0-255</format>
              <description>ICMPv6 type number</description>
            </valueHelp>
            <valueHelp>
              <format>txt</format>
              <description>ICMPv6 type name (e.g. echo-request)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-255"/>
              <regex>(destination-unreachable|packet-too-big|time-exceeded|parameter-problem|echo-request|echo-reply|mld-listener-query|mld-listener-report|mld-listener-done|mld-listener-reduction|nd-router-solicit|nd-router-advert|nd-neighbor-solicit|nd-neighbor-advert|nd-redirect|router-renumbering|ind-neighbor-solicit|ind-neighbor-advert|mld2-listener-report)</regex>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="icmpv6-code">
          <properties>
            <help>ICMPv6 code</help>
            <valueHelp>
              <format>u32:0-255</format>
              <description>ICMPv6 code (must be valid for the selected icmpv6-type)</description>
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
