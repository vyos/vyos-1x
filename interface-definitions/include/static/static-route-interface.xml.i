<!-- include start from static/static-route-interface.xml.i -->
<leafNode name="interface">
  <properties>
    <help>Gateway interface name</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces.py</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Gateway interface name</description>
    </valueHelp>
    <constraint>
      <validator name="interface-name"/>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
