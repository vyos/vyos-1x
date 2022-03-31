<!-- include start from interface/redirect.xml.i -->
<leafNode name="redirect">
  <properties>
    <help>Incoming packet redirection destination</help>
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
  </properties>
</leafNode>
<!-- include end -->
