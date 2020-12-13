<!-- included start from tunnel-local-remote-ip.xml.i -->
<leafNode name="local-ip">
  <properties>
    <help>Local IP address for this tunnel</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Local IPv4 address for this tunnel</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>Local IPv6 address for this tunnel</description>
    </valueHelp>
    <completionHelp>
      <script>${vyos_completion_dir}/list_local_ips.sh --both</script>
    </completionHelp>
    <constraint>
      <validator name="ip-address"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="remote-ip">
  <properties>
    <help>Remote IP address for this tunnel</help>
    <valueHelp>
      <format>ipv4</format>
      <description>Remote IPv4 address for this tunnel</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>Remote IPv6 address for this tunnel</description>
    </valueHelp>
    <constraint>
      <!-- does it need fixing/changing to be more restrictive ? -->
      <validator name="ip-address"/>
    </constraint>
  </properties>
</leafNode>
