<!-- include start from source-interface-ethernet.xml.i -->
<leafNode name="source-interface">
  <properties>
    <help>Physical interface the traffic will go through</help>
    <valueHelp>
      <format>interface</format>
      <description>Physical interface used for traffic forwarding</description>
    </valueHelp>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces --type ethernet</script>
    </completionHelp>
  </properties>
</leafNode>
<!-- include end -->
