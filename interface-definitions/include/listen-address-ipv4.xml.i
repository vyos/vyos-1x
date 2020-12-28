<!-- included start from listen-address-ipv4.xml.i -->
<leafNode name="listen-address">
  <properties>
    <help>Local IPv4 addresses for service to listen on</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_local_ips.sh --ipv4</script>
    </completionHelp>
    <valueHelp>
      <format>ipv4</format>
      <description>IP address to listen for incoming connections</description>
    </valueHelp>
    <multi/>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- included end -->
