<!-- include start from dhcp/option-v4.xml.i -->
<node name="option">
  <properties>
    <help>DHCP option</help>
  </properties>
  <children>
    #include <include/dhcp/captive-portal.xml.i>
    #include <include/dhcp/domain-name.xml.i>
    #include <include/dhcp/domain-search.xml.i>
    #include <include/dhcp/ntp-server.xml.i>
    #include <include/name-server-ipv4.xml.i>
    <leafNode name="bootfile-name">
      <properties>
        <help>Bootstrap file name</help>
        <constraint>
          <regex>[[:ascii:]]{1,253}</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="bootfile-server">
      <properties>
        <help>Server from which the initial boot file is to be loaded</help>
        <valueHelp>
          <format>ipv4</format>
          <description>Bootfile server IPv4 address</description>
        </valueHelp>
        <valueHelp>
          <format>hostname</format>
          <description>Bootfile server FQDN</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
          <validator name="fqdn"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="bootfile-size">
      <properties>
        <help>Bootstrap file size</help>
        <valueHelp>
          <format>u32:1-16</format>
          <description>Bootstrap file size in 512 byte blocks</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-16"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="client-prefix-length">
      <properties>
        <help>Specifies the clients subnet mask as per RFC 950. If unset, subnet declaration is used.</help>
        <valueHelp>
          <format>u32:0-32</format>
          <description>DHCP client prefix length must be 0 to 32</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-32"/>
        </constraint>
        <constraintErrorMessage>DHCP client prefix length must be 0 to 32</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="default-router">
      <properties>
        <help>IP address of default router</help>
        <valueHelp>
          <format>ipv4</format>
          <description>Default router IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="ip-forwarding">
      <properties>
        <help>Enable IP forwarding on client</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="ipv6-only-preferred">
      <properties>
        <help>Disable IPv4 on IPv6 only hosts (RFC 8925)</help>
        <valueHelp>
          <format>u32</format>
          <description>Seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
        <constraintErrorMessage>Seconds must be between 0 and 4294967295 (49 days)</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="pop-server">
      <properties>
        <help>IP address of POP3 server</help>
        <valueHelp>
          <format>ipv4</format>
          <description>POP3 server IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="server-identifier">
      <properties>
        <help>Address for DHCP server identifier</help>
        <valueHelp>
          <format>ipv4</format>
          <description>DHCP server identifier IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="smtp-server">
      <properties>
        <help>IP address of SMTP server</help>
        <valueHelp>
          <format>ipv4</format>
          <description>SMTP server IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <tagNode name="static-route">
      <properties>
        <help>Classless static route destination subnet</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 address and prefix length</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-prefix"/>
        </constraint>
      </properties>
      <children>
        <leafNode name="next-hop">
          <properties>
            <help>IP address of router to be used to reach the destination subnet</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IPv4 address of router</description>
            </valueHelp>
            <constraint>
              <validator name="ip-address"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </tagNode >
    <leafNode name="tftp-server-name">
      <properties>
        <help>TFTP server name</help>
        <valueHelp>
          <format>ipv4</format>
          <description>TFTP server IPv4 address</description>
        </valueHelp>
        <valueHelp>
          <format>hostname</format>
          <description>TFTP server FQDN</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
          <validator name="fqdn"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="time-offset">
      <properties>
        <help>Client subnet offset in seconds from Coordinated Universal Time (UTC)</help>
        <valueHelp>
          <format>[-]N</format>
          <description>Time offset (number, may be negative)</description>
        </valueHelp>
        <constraint>
          <regex>-?[0-9]+</regex>
        </constraint>
        <constraintErrorMessage>Invalid time offset value</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="time-server">
      <properties>
        <help>IP address of time server</help>
        <valueHelp>
          <format>ipv4</format>
          <description>Time server IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="time-zone">
      <properties>
        <help>Time zone to send to clients. Uses RFC4833 options 100 and 101</help>
        <completionHelp>
          <script>timedatectl list-timezones</script>
        </completionHelp>
        <constraint>
          <validator name="timezone" argument="--validate"/>
        </constraint>
      </properties>
    </leafNode>
    <node name="vendor-option">
      <properties>
        <help>Vendor Specific Options</help>
      </properties>
      <children>
        <node name="ubiquiti">
          <properties>
            <help>Ubiquiti specific parameters</help>
          </properties>
          <children>
            <leafNode name="unifi-controller">
              <properties>
                <help>Address of UniFi controller</help>
                <valueHelp>
                  <format>ipv4</format>
                  <description>IP address of UniFi controller</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv4-address"/>
                </constraint>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
    <leafNode name="wins-server">
      <properties>
        <help>IP address for Windows Internet Name Service (WINS) server</help>
        <valueHelp>
          <format>ipv4</format>
          <description>WINS server IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="wpad-url">
      <properties>
        <help>Web Proxy Autodiscovery (WPAD) URL</help>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
