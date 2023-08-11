<!-- include start from firewall/match-interface.xml.i -->
<leafNode name="interface-name">
  <properties>
    <help>Match interface</help>
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
  </properties>
</leafNode>
<leafNode name="interface-group">
  <properties>
    <help>Match interface-group</help>
    <completionHelp>
      <path>firewall group interface-group</path>
    </completionHelp>
  </properties>
</leafNode>
<!-- include end -->