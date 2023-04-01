<!-- include start from static/static-route-interface.xml.i -->
<leafNode name="interface">
  <properties>
    <help>Gateway interface name</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Gateway interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
