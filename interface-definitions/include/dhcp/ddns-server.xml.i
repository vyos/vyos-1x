<!-- include start from dhcp/ddns-server.xml.i -->
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
    <leafNode name="address">
      <properties>
        <help>DNS server IP address</help>
        <valueHelp>
          <format>ipv4</format>
          <description>DNS server IP address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
    </leafNode>
    #include <include/port-number.xml.i>
    <leafNode name="port">
      <defaultValue>53</defaultValue>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
