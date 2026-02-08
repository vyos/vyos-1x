<!-- include start from dhcp/dnr-v4.xml.i -->
<tagNode name="dnr">
  <properties>
    <help>Discovery of Network-designated Resolvers (DNR)</help>
    <valueHelp>
      <format>u32:1-9999</format>
      <description>DNR instance identifier</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-9999"/>
    </constraint>
    <constraintErrorMessage>DNR instance identifier must be between 1 and 9999</constraintErrorMessage>
  </properties>
  <children>
    #include <include/dhcp/dnr-common.xml.i>
    <leafNode name="address">
      <properties>
        <help>IPv4 address of encrypted DNS resolver</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 resolver address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    #include <include/dhcp/dnr-service-parameters.xml.i>
  </children>
</tagNode>
<!-- include end -->
