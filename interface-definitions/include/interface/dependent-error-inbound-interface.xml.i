<!-- include start from interface/dependent-error-inbound-interface.xml.i -->
<leafNode name="inbound-interface">
  <properties>
  <help>Inbound Interface</help>
  <completionHelp>
    <script>${vyos_completion_dir}/list_interfaces</script>
  </completionHelp>
  <dependency kind="interface" alert="error"/>
  </properties>
</leafNode>
<!-- include end -->
