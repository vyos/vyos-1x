<!-- include start from policy/local-route_rule_protocol.xml.i -->
<leafNode name="protocol">
  <properties>
    <help>Protocol to match (protocol name or number)</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_protocols.sh</script>
    </completionHelp>
    <valueHelp>
      <format>u32:0-255</format>
      <description>IP protocol number</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;protocol&gt;</format>
      <description>IP protocol name</description>
    </valueHelp>
    <constraint>
      <validator name="ip-protocol"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
