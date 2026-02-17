<!-- include start from serial/service/slip.xml.i -->
<node name="slip">
  <properties>
    <help>SLIP profile</help>
  </properties>
  <children>
    <leafNode name="local-address">
      <properties>
        <help>The IPV4 IP address of the IGOS end of the SLIP link</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 address and prefix length</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-host"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="remote-address">
      <properties>
        <help>The IPV4 IP address of the remote end of the SLIP link</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 address and prefix length</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-host"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="mtu">
      <properties>
        <help>The Maximum Transmission Unit (MTU) parameter restricts the size of individual SLIP packets being sent by the IOLAN</help>
        <valueHelp>
          <format>u32:256-1006</format>
          <description>(in bytes)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 256-1006"/>
        </constraint>
      </properties>
      <defaultValue>256</defaultValue>
    </leafNode>
    <leafNode name="disable-vj-comp">
      <properties>
        <help>Disable Van Jacobson style TCP/IP header compression in both the transmit and the receive direction</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
