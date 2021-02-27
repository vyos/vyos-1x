<!-- included start from tunnel-local-remote-ip.xml.i -->
#include <include/source-address-ipv4-ipv6.xml.i>
<leafNode name="remote-ip">
  <properties>
    <help>Remote IP address for this tunnel</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Remote IPv4 address for this tunnel</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>Remote IPv6 address for this tunnel</description>
    </valueHelp>
    <constraint>
      <!-- does it need fixing/changing to be more restrictive ? -->
      <validator name="ip-address"/>
    </constraint>
  </properties>
</leafNode>
