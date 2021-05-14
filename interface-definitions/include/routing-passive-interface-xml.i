<!-- include start from routing-passive-interface-xml.i -->
<leafNode name="passive-interface">
  <properties>
    <help>Suppress routing updates on an interface</help>
    <completionHelp>
      <list>default</list>
      <script>${vyos_completion_dir}/list_interfaces.py</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface to be passive (i.e. suppress routing updates)</description>
    </valueHelp>
    <valueHelp>
      <format>default</format>
      <description>Default to suppress routing updates on all interfaces</description>
    </valueHelp>
    <constraint>
      <regex>^(default)$</regex>
      <validator name="interface-name"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
