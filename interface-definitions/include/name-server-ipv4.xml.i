<!-- include start from name-server-ipv4.xml.i -->
<leafNode name="name-server">
  <properties>
    <help>Domain Name Servers (DNS) addresses</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Domain Name Server (DNS) IPv4 address</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
