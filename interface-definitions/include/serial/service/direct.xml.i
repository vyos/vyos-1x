<!-- include start from serial/service/direct.xml.i -->
<node name="direct">
  <properties>
    <help>Direct connection profile</help>
  </properties>
  <children>
    <leafNode name="main-hostport">
      <properties>
        <help>Connect to main host port</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Port number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="main-hostname">
      <properties>
        <help>Connect to main host</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IP address of main host</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address of main host</description>
        </valueHelp>
        <valueHelp>
          <format>hostname</format>
          <description>Fully qualified host name of main host</description>
        </valueHelp>
        <constraint>
          <validator name="ip-address"/>
          <validator name="fqdn"/>
        </constraint>
      </properties>
    </leafNode>
    <node name="multihost">
      <properties>
        <help>Connect to multiple hosts [tcp only]</help>
      </properties>
      <children>
        #include <include/serial/service/utils/multihost.xml.i>
      </children>
    </node>
    <leafNode name="initiate-any-char">
      <properties>
        <help>Connect when any data is received [main only]</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="initiate-specific-char">
      <properties>
        <help>Connect when specific character received [main only]</help>
        <valueHelp>
          <format>txt</format>
          <description>ASCII char in hex value</description>
        </valueHelp>
        <constraint>
          <validator name="hex"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
