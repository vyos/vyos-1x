<!-- include start from generic-interface-multi.xml.i -->
<leafNode name="interface">
  <properties>
    <help>Interface to use</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces.py</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      <validator name="interface-name"/>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
