<!-- include start from bgp/neighbor-update-source.xml.i -->
<leafNode name="update-source">
  <!-- Need to check format interfaces -->
  <properties>
    <help>Source IP of routing updates</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_local_ips.sh --both</script>
      <script>${vyos_completion_dir}/list_interfaces</script>
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
      <validator name="ip-address"/>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
