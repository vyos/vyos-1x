<!-- include start from interface/mirror.xml.i -->
<node name="mirror">
  <properties>
    <help>Mirror ingress/egress packets</help>
  </properties>
  <children>
    <leafNode name="ingress">
      <properties>
        <help>Mirror ingress traffic to destination interface</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces</script>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Destination interface name</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="egress">
      <properties>
        <help>Mirror egress traffic to destination interface</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces</script>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Destination interface name</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
