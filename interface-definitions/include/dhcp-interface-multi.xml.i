<!-- include start from dhcp-interface-multi.xml.i -->
<leafNode name="dhcp-interface">
  <properties>
    <help>DHCP interface supplying next-hop IP address</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>DHCP interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->