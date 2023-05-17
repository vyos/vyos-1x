<!-- include start from name-server-ipv4-ipv6.xml.i -->
<leafNode name="name-server">
  <properties>
    <help>Domain Name Servers (DNS) addresses</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Domain Name Server (DNS) IPv4 address</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>Domain Name Server (DNS) IPv6 address</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
