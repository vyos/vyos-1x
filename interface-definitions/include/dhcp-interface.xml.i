    <leafNode name="dhcp-interface">
      <properties>
        <help>DHCP interface supplying next-hop IP address</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces.py</script>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>DHCP interface name</description>
        </valueHelp>
        <constraint>
          <validator name="interface-name"/>
        </constraint>
      </properties>
    </leafNode>
