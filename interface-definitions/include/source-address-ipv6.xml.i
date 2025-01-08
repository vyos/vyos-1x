<!-- include start from source-address-ipv6.xml.i -->
<leafNode name="source-address">
  <properties>
    <help>IPv6 address used to initiate connection</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_local_ips.sh --ipv6</script>
    </completionHelp>
    <valueHelp>
      <format>ipv6</format>
      <description>IPv6 source address</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6-address"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
