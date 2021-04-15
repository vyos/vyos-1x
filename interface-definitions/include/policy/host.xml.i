<!-- include start from policy/host.xml.i -->
<leafNode name="host">
  <properties>
    <help>Single host IP address to match</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Host address to match</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
