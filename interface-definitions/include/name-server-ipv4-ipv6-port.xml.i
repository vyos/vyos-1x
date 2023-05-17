<!-- include start from name-server-ipv4-ipv6-port.xml.i -->
<tagNode name="name-server">
  <properties>
    <help>Domain Name Servers (DNS) addresses to forward queries to</help>
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
  </properties>
  <children>
    #include <include/port-number.xml.i>
    <leafNode name="port">
      <defaultValue>53</defaultValue>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
