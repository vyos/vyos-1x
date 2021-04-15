<!-- include start from policy/inverse-mask.xml.i -->
<leafNode name="inverse-mask">
  <properties>
    <help>Network/netmask to match (requires network be defined)</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Inverse-mask to match</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
