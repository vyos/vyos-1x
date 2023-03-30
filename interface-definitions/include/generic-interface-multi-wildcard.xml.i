
<!-- include start from generic-interface-multi-wildcard.xml.i -->
<leafNode name="interface">
  <properties>
    <help>Interface name to apply policy route configuration</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name-with-wildcard.xml.in>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
