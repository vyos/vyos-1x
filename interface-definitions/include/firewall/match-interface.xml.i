<!-- include start from firewall/match-interface.xml.i -->
<leafNode name="interface-name">
  <properties>
    <help>Match interface</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <valueHelp>
      <format>txt*</format>
      <description>Interface name with wildcard</description>
    </valueHelp>
    <valueHelp>
      <format>!txt</format>
      <description>Inverted interface name to match</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name-with-wildcard-and-inverted.xml.i>
    </constraint>
  </properties>
</leafNode>
<leafNode name="interface-group">
  <properties>
    <help>Match interface-group</help>
    <completionHelp>
      <path>firewall group interface-group</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface-group name to match</description>
    </valueHelp>
    <valueHelp>
      <format>!txt</format>
      <description>Inverted interface-group name to match</description>
    </valueHelp>
  </properties>
</leafNode>
<!-- include end -->