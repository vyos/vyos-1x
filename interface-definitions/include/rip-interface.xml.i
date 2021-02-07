<!-- included start from rip-interface.xml.i -->
<leafNode name="interface">
  <properties>
    <help>Interface name</help>
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
<!-- included end -->
