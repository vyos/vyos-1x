<!-- include start from dhcp/ddns-dns-server.xml.i -->
<tagNode name="dns-server">
  <properties>
    <help>DNS server specification</help>
    <valueHelp>
      <format>u32:1-999999</format>
      <description>Number for this DNS server</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-999999"/>
    </constraint>
    <constraintErrorMessage>DNS server number must be between 1 and 999999</constraintErrorMessage>
  </properties>
  <children>
    #include <include/address-ipv4-ipv6-single.xml.i>
    #include <include/port-number.xml.i>
  </children>
</tagNode>
<!-- include end -->
