<!-- included start from interface-mirror.xml.i -->
<node name="mirror">
  <properties>
    <help>Incoming/outgoing packet mirroring destination</help>
  </properties>
  <children>
    <leafNode name="ingress">
      <properties>
        <help>Mirror the ingress traffic of the interface to the destination interface</help>
        <completionHelp>
            <script>${vyos_completion_dir}/list_interfaces.py</script>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="egress">
      <properties>
        <help>Mirror the egress traffic of the interface to the destination interface</help>
        <completionHelp>
            <script>${vyos_completion_dir}/list_interfaces.py</script>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- included end -->
