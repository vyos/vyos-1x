<!-- include start from source-interface-broadcast.xml.i -->
<leafNode name="source-interface">
  <properties>
    <help>Physical interface the traffic will go through</help>
    <valueHelp>
      <format>interface</format>
      <description>Interface name</description>
    </valueHelp>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces --broadcast</script>
    </completionHelp>
  </properties>
</leafNode>
<!-- include end -->
