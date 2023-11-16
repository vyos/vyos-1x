<!-- include start from rip/interface.xml.i -->
<tagNode name="interface">
  <properties>
    <help>Interface name</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
  </properties>
  <children>
    <node name="split-horizon">
      <properties>
        <help>Split horizon parameters</help>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        <leafNode name="poison-reverse">
          <properties>
            <help>Disable split horizon on specified interface</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</tagNode>
<!-- include end -->
