<!-- include start from interface/redirect.xml.i -->
<leafNode name="redirect">
  <properties>
    <help>Redirect incoming packet to destination</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Destination interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
