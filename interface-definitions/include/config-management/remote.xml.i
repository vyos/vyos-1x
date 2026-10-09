<!-- include start from config-management/remote.xml.i -->
<leafNode name="server">
  <properties>
    <help>Remote server to connect to</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Server IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>Server IPv6 address</description>
    </valueHelp>
    <valueHelp>
      <format>hostname</format>
      <description>Server hostname/FQDN</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
      <validator name="fqdn"/>
    </constraint>
    <constraintErrorMessage>Server must be an IPv4/IPv6 address or a hostname</constraintErrorMessage>
  </properties>
</leafNode>
#include <include/port-number.xml.i>
<leafNode name="path">
  <properties>
    <help>Remote path used to store the archived configuration</help>
    <valueHelp>
      <format>txt</format>
      <description>Remote path</description>
    </valueHelp>
  </properties>
</leafNode>
<!-- include end -->
