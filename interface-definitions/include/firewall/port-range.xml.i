<!-- include start from firewall/port-range.xml.i -->
<leafNode name="port">
  <properties>
    <help>Port</help>
    <valueHelp>
      <format>txt</format>
      <description>Named port (any name in /etc/services, e.g., http)</description>
    </valueHelp>
    <valueHelp>
      <format>u32:1-65535</format>
      <description>Numbered port</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;start-end&gt;</format>
      <description>Numbered port range (e.g. 1001-1005)</description>
    </valueHelp>
    <constraint>
      <validator name="port-range"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
