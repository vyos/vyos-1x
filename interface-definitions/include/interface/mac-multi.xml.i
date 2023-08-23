<!-- include start from interface/mac-multi.xml.i -->
<leafNode name="mac">
  <properties>
    <help>Media Access Control (MAC) address</help>
    <valueHelp>
      <format>macaddr</format>
      <description>Hardware (MAC) address</description>
    </valueHelp>
    <constraint>
      <validator name="mac-address"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
