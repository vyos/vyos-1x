<!-- include start from interface/hw-id.xml.i -->
<leafNode name="hw-id">
  <properties>
    <help>Associate Ethernet Interface with given Media Access Control (MAC) address</help>
    <valueHelp>
      <format>macaddr</format>
      <description>Hardware (MAC) address</description>
    </valueHelp>
    <constraint>
      <validator name="mac-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
