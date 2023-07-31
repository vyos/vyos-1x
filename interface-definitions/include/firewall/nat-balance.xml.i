<!-- include start from firewall/nat-balance.xml.i -->
<tagNode name="backend">
  <properties>
    <help>Translated IP address</help>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address to match</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
  <children>
    <leafNode name="weight">
      <properties>
        <help>Set probability for this output value</help>
        <valueHelp>
          <format>u32:1-100</format>
          <description>Set probability for this output value</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--allow-range --range 1-100"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->