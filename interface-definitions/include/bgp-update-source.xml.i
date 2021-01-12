<!-- included start from bgp-update-source.xml.i -->
<leafNode name="update-source">
  <!-- Need to check format interfaces -->
  <properties>
    <help>Source IP of routing updates</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_local_ips.sh --both</script>
    </completionHelp>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 address of route source</description>
    </valueHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 address of route source</description>
    </valueHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface as route source</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
      <validator name="ipv6-address"/>
      <regex>^(br|bond|dum|en|eth|gnv|peth|tun|vti|vxlan|wg|wlan)[0-9]+|lo$</regex>
    </constraint>
  </properties>
</leafNode>
<!-- included end -->
