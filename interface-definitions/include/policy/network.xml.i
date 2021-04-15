<!-- include start from policy/network.xml.i -->
<leafNode name="network">
  <properties>
    <help>Network/netmask to match (requires inverse-mask be defined)</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>Inverse-mask to match</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
