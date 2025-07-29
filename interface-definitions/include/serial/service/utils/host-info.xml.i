<!-- include start from serial/service/utils/host-info.xml.i -->
<leafNode name="connect-hostport">
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
<leafNode name="connect-hostname">
  <properties>
    <help>Connect to host</help>
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
<!-- include end -->
