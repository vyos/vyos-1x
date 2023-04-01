<!-- include start from source-interface.xml.i -->
<leafNode name="source-interface">
  <properties>
    <help>Interface used to establish connection</help>
    <valueHelp>
      <format>interface</format>
      <description>Interface name</description>
    </valueHelp>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
