<!-- include start from qos/match.xml.i -->
<tagNode name="match">
  <properties>
    <help>Class matching rule name</help>
    <constraint>
      <regex>[^-].*</regex>
    </constraint>
    <constraintErrorMessage>Match queue name cannot start with hyphen (-)</constraintErrorMessage>
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
    <node name="ip">
      <properties>
        <help>Match IP protocol header</help>
      </properties>
      <children>
        <node name="destination">
          <properties>
            <help>Match on destination port or address</help>
          </properties>
          <children>
            <leafNode name="address">
              <properties>
                <help>IPv4 destination address for this match</help>
                <valueHelp>
                  <format>ipv4net</format>
                  <description>IPv4 address and prefix length</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv4"/>
                </constraint>
              </properties>
            </leafNode>
            #include <include/port-number.xml.i>
          </children>
        </node>
        #include <include/qos/dscp.xml.i>
        #include <include/qos/max-length.xml.i>
        #include <include/ip-protocol.xml.i>
        <node name="source">
          <properties>
            <help>Match on source port or address</help>
          </properties>
          <children>
            <leafNode name="address">
              <properties>
                <help>IPv4 source address for this match</help>
                <valueHelp>
                  <format>ipv4net</format>
                  <description>IPv4 address and prefix length</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv4"/>
                </constraint>
              </properties>
            </leafNode>
            #include <include/port-number.xml.i>
          </children>
        </node>
        #include <include/qos/tcp-flags.xml.i>
      </children>
    </node>
    <node name="ipv6">
      <properties>
        <help>Match IPv6 protocol header</help>
      </properties>
      <children>
        <node name="destination">
          <properties>
            <help>Match on destination port or address</help>
          </properties>
          <children>
            <leafNode name="address">
              <properties>
                <help>IPv6 destination address for this match</help>
                <valueHelp>
                  <format>ipv6net</format>
                  <description>IPv6 address and prefix length</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv6"/>
                </constraint>
              </properties>
            </leafNode>
            #include <include/port-number.xml.i>
          </children>
        </node>
        #include <include/qos/dscp.xml.i>
        #include <include/qos/max-length.xml.i>
        #include <include/ip-protocol.xml.i>
        <node name="source">
          <properties>
            <help>Match on source port or address</help>
          </properties>
          <children>
            <leafNode name="address">
              <properties>
                <help>IPv6 source address for this match</help>
                <valueHelp>
                  <format>ipv6net</format>
                  <description>IPv6 address and prefix length</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv6"/>
                </constraint>
              </properties>
            </leafNode>
            #include <include/port-number.xml.i>
          </children>
        </node>
        #include <include/qos/tcp-flags.xml.i>
      </children>
    </node>
    <leafNode name="mark">
      <properties>
        <help>Match on mark applied by firewall</help>
        <valueHelp>
          <format>txt</format>
          <description>FW mark to match</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0x0-0xffff"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="vif">
      <properties>
        <help>Virtual Local Area Network (VLAN) ID for this match</help>
        <valueHelp>
          <format>u32:0-4095</format>
          <description>Virtual Local Area Network (VLAN) tag </description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4095"/>
        </constraint>
        <constraintErrorMessage>VLAN ID must be between 0 and 4095</constraintErrorMessage>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
