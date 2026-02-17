<!-- include start from serial/service/general/vmodem-phonebook.xml.i -->
<node name="vmodem-phone-list">
  <properties>
    <help>Phone number to host mapping</help>
  </properties>
  <children>
    <tagNode name="entry">
      <properties>
        <help>Phonebook entry</help>
        <valueHelp>
          <format>u32:1-8</format>
          <description>Entry ID (1-8)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-8"/>
        </constraint>
      </properties>
      <children>
        <leafNode name="hostname">
          <properties>
            <help>Mapped host name</help>
            <valueHelp>
              <format>ipv4</format>
              <description>IP address of current host</description>
            </valueHelp>
            <valueHelp>
              <format>ipv6</format>
              <description>IPv6 address of current host</description>
            </valueHelp>
            <valueHelp>
              <format>hostname</format>
              <description>Fully qualified host name of current host</description>
            </valueHelp>
            <constraint>
              <validator name="ip-address"/>
              <validator name="fqdn"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="port">
          <properties>
            <help>Mapped tcp port</help>
            <valueHelp>
              <format>u32:1-65535</format>
              <description>Port number</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-65535"/>
            </constraint>
          </properties>
        </leafNode>
        <leafNode name="phone-number">
          <properties>
            <help>Phone number</help>
            <constraint>
              <regex>.{0,31}</regex>
            </constraint>
            <constraintErrorMessage>Phone number too long (limit 31 characters)</constraintErrorMessage>
          </properties>
        </leafNode>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
