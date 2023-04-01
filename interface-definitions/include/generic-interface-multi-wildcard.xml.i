<!-- include start from generic-interface-multi-wildcard.xml.i -->
<leafNode name="interface">
  <properties>
    <help>Interface to use</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name, wildcard (*) supported</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name-with-wildcard.xml.i>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
