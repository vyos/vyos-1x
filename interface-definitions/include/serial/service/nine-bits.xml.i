<!-- include start from serial/service/nine-bits.xml.i -->
<node name="nine-bits">
  <properties>
    <help>Nine bits profile</help>
  </properties>
  <children>
    <leafNode name="start-trigger-hex-string">
      <properties>
        <help>Hex string to start nine bits protocol</help>
        <valueHelp>
          <format>txt</format>
          <description>2 hex value written with 4 digits</description>
        </valueHelp>
        <constraint>
          <validator name="2hex"/>
        </constraint>
      </properties>
      <defaultValue>0000</defaultValue>
    </leafNode>
    <leafNode name="stop-trigger-hex-string">
      <properties>
        <help>Hex string to stop nine bits protocol</help>
        <valueHelp>
          <format>txt</format>
          <description>2 hex value written with 4 digits</description>
        </valueHelp>
        <constraint>
          <validator name="2hex"/>
        </constraint>
      </properties>
      <defaultValue>0000</defaultValue>
    </leafNode>
    <leafNode name="trigger">
      <properties>
        <help>Enable using trigger to control nine bits protocol</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="delay">
      <properties>
        <help>The delay between writing first byte and rest of message to the serial port</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Specifies the delay in milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
    <leafNode name="hostport">
      <properties>
        <help>Connect to host port</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Port number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="hostname">
      <properties>
        <help>Connect to host name</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IP address of host</description>
        </valueHelp>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address of host</description>
        </valueHelp>
        <valueHelp>
          <format>hostname</format>
          <description>Fully qualified host name of host</description>
        </valueHelp>
        <constraint>
          <validator name="ip-address"/>
          <validator name="fqdn"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
