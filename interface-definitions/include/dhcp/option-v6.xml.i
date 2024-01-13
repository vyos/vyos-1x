<!-- include start from dhcp/option-v6.xml.i -->
<node name="option">
  <properties>
    <help>DHCPv6 option</help>
  </properties>
  <children>
    #include <include/dhcp/captive-portal.xml.i>
    #include <include/dhcp/domain-search.xml.i>
    #include <include/name-server-ipv6.xml.i>
    <leafNode name="nis-domain">
      <properties>
        <help>NIS domain name for client to use</help>
        <constraint>
          #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
        </constraint>
        <constraintErrorMessage>Invalid NIS domain name</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="nis-server">
      <properties>
        <help>IPv6 address of a NIS Server</help>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address of NIS server</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="nisplus-domain">
      <properties>
        <help>NIS+ domain name for client to use</help>
        <constraint>
          #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
        </constraint>
        <constraintErrorMessage>Invalid NIS+ domain name. May only contain letters, numbers and .-_</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="nisplus-server">
      <properties>
        <help>IPv6 address of a NIS+ Server</help>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address of NIS+ server</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="sip-server">
      <properties>
        <help>IPv6 address of SIP server</help>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address of SIP server</description>
        </valueHelp>
        <valueHelp>
          <format>hostname</format>
          <description>FQDN of SIP server</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-address"/>
          <validator name="fqdn"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="sntp-server">
      <properties>
        <help>IPv6 address of an SNTP server for client to use</help>
        <constraint>
          <validator name="ipv6-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <node name="vendor-option">
      <properties>
        <help>Vendor Specific Options</help>
      </properties>
      <children>
        <node name="cisco">
          <properties>
            <help>Cisco specific parameters</help>
          </properties>
          <children>
            <leafNode name="tftp-server">
              <properties>
                <help>TFTP server name</help>
                <valueHelp>
                  <format>ipv6</format>
                  <description>TFTP server IPv6 address</description>
                </valueHelp>
                <constraint>
                  <validator name="ipv6-address"/>
                </constraint>
                <multi/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
