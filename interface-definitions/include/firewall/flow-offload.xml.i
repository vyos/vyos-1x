<!-- include start from firewall/flow-offload.xml.i -->
<node name="flow-offload">
  <properties>
    <help>Configurable flow offload options</help>
  </properties>
  <children>
    <leafNode name="disable">
      <properties>
        <help>Disable flow offload</help>
        <valueless/>
      </properties>
    </leafNode>
    <node name="software">
      <properties>
        <help>Software offload</help>
      </properties>
      <children>
        <leafNode name="interface">
          <properties>
            <help>Interfaces to enable</help>
            <completionHelp>
              <script>${vyos_completion_dir}/list_interfaces</script>
            </completionHelp>
            <multi/>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="hardware">
      <properties>
        <help>Hardware offload</help>
      </properties>
      <children>
        <leafNode name="interface">
          <properties>
            <help>Interfaces to enable</help>
            <completionHelp>
              <script>${vyos_completion_dir}/list_interfaces</script>
            </completionHelp>
            <multi/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
