<!-- include start from source-address-ipv4.xml.i -->
<leafNode name="source-address">
  <properties>
    <help>IPv4 source address used to initiate connection</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_local_ips.sh --ipv4</script>
    </completionHelp>
    <valueHelp>
      <format>ipv4</format>
      <description>IPv4 source address</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
