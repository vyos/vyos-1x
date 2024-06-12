<!-- include start from firewall/protocol.xml.i -->
<leafNode name="protocol">
  <properties>
    <help>Protocol to match (protocol name, number, or "all")</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_protocols.sh</script>
      <list>all tcp_udp</list>
    </completionHelp>
    <valueHelp>
      <format>all</format>
      <description>All IP protocols</description>
    </valueHelp>
    <valueHelp>
      <format>tcp_udp</format>
      <description>Both TCP and UDP</description>
    </valueHelp>
    <valueHelp>
      <format>u32:0-255</format>
      <description>IP protocol number</description>
    </valueHelp>
    <valueHelp>
      <format>&lt;protocol&gt;</format>
      <description>IP protocol name</description>
    </valueHelp>
    <valueHelp>
      <format>!&lt;protocol&gt;</format>
      <description>IP protocol name</description>
    </valueHelp>
    <constraint>
      <validator name="ip-protocol"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->