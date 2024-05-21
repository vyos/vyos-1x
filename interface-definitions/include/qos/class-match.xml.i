<!-- include start from qos/class-match.xml.i -->
<tagNode name="match">
  <properties>
    <help>Class matching rule name</help>
    <constraint>
      <regex>[^-].*</regex>
    </constraint>
    <constraintErrorMessage>Match queue name cannot start with hyphen</constraintErrorMessage>
  </properties>
  <children>
    #include <include/generic-description.xml.i>
    <node name="ether">
      <properties>
        <help>Ethernet header match</help>
      </properties>
      <children>
        <leafNode name="destination">
          <properties>
            <help>Ethernet destination address for this match</help>
            <valueHelp>
              <format>macaddr</format>
              <description>MAC address to match</description>
            </valueHelp>
            <constraint>
              <validator name="mac-address"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="protocol">
          <properties>
            <help>Ethernet protocol for this match</help>
            <!-- this refers to /etc/protocols -->
            <completionHelp>
              <list>all 802.1Q 802_2 802_3 aarp aoe arp atalk dec ip ipv6 ipx lat localtalk rarp snap x25</list>
            </completionHelp>
            <valueHelp>
              <format>u32:0-65535</format>
              <description>Ethernet protocol number</description>
            </valueHelp>
            <valueHelp>
              <format>txt</format>
              <description>Ethernet protocol name</description>
            </valueHelp>
            <valueHelp>
              <format>all</format>
              <description>Any protocol</description>
            </valueHelp>
            <valueHelp>
              <format>ip</format>
              <description>Internet IP (IPv4)</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6</format>
              <description>Internet IP (IPv6)</description>
            </valueHelp>
            <valueHelp>
              <format>arp</format>
              <description>Address Resolution Protocol</description>
            </valueHelp>
            <valueHelp>
              <format>atalk</format>
              <description>Appletalk</description>
            </valueHelp>
            <valueHelp>
              <format>ipx</format>
              <description>Novell Internet Packet Exchange</description>
            </valueHelp>
            <valueHelp>
              <format>802.1Q</format>
              <description>802.1Q VLAN tag</description>
            </valueHelp>
            <constraint>
              <validator name="ip-protocol"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="source">
          <properties>
            <help>Ethernet source address for this match</help>
            <valueHelp>
              <format>macaddr</format>
              <description>MAC address to match</description>
            </valueHelp>
            <constraint>
              <validator name="mac-address"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
    #include <include/generic-interface.xml.i>
    #include <include/qos/class-match-ipv4.xml.i>
    #include <include/qos/class-match-ipv6.xml.i>
    #include <include/qos/class-match-mark.xml.i>
    #include <include/qos/class-match-vif.xml.i>
  </children>
</tagNode>
<!-- include end -->
