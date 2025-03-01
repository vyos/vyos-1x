<!-- included start from network-event-type-interface.xml.i -->
<tagNode name="interface">
  <properties>
    <help>Show log for specific interface</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
  </properties>
  <command>journalctl --no-hostname --boot --unit vyos-network-event-logger.service | grep "$(echo "\[$4\]" | tr '[:lower:]' '[:upper:]')" | grep "\b$6\b"</command>
</tagNode>
<!-- included end -->
