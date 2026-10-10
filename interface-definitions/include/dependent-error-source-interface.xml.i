<!-- include start from dependent-error-source-interface.xml.i -->
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
    <dependency kind="interface" alert="error"/>
  </properties>
</leafNode>
<!-- include end -->
