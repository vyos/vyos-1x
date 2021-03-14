<!-- include start from accel-ppp/wins-server.xml.i -->
<leafNode name="wins-server">
  <properties>
    <help>Windows Internet Name Service (WINS) servers propagated to client</help>
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
