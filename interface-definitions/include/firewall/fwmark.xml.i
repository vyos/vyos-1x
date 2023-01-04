<!-- include start from firewall/fwmark.xml.i -->
<leafNode name="fwmark">
  <properties>
    <help>Match fwmark value</help>
    <valueHelp>
      <format>u32:1-2147483647</format>
      <description>Match firewall mark value</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-2147483647"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
