<!-- include start from listen-address-single.xml.i -->
<leafNode name="listen-address">
  <properties>
    <help>Local IP addresses to listen on</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_local_ips.sh --both</script>
    </completionHelp>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address to listen for incoming connections</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 address to listen for incoming connections</description>
    </valueHelp>
    <constraint>
      <validator name="ip-address"/>
      <validator name="ipv6-link-local"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
