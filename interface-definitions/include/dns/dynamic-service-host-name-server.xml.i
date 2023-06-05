<!-- include start from dns/dynamic-service-host-name-server.xml.i -->
<leafNode name="host-name">
  <properties>
    <help>Hostname to register with Dynamic DNS service</help>
    <constraint>
        #include <include/constraint/host-name.xml.i>
    </constraint>
    <constraintErrorMessage>Host-name must be alphanumeric and can contain hyphens</constraintErrorMessage>
    <multi/>
  </properties>
</leafNode>
<leafNode name="server">
  <properties>
    <help>Remote Dynamic DNS server to send updates to</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address of the remote server</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 address of the remote server</description>
    </valueHelp>
    <valueHelp>
      <format>hostname</format>
      <description>Fully qualified domain name of the remote server</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
      <validator name="fqdn"/>
    </constraint>
    <constraintErrorMessage>Remote server must be IP address or fully qualified domain name</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
