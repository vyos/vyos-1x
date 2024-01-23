<!-- include start from listen-interface-multi-broadcast.xml.i -->
<leafNode name="listen-interface">
  <properties>
    <help>Interface to listen on</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces --broadcast</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
    <multi/>
  </properties>
</leafNode>
<!-- include end -->
