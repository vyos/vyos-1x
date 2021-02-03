<!-- included start from static-route-next-hop-interface.xml.i -->
<leafNode name="interface">
  <properties>
    <help>Gateway interface name</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces.py</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Gateway interface name</description>
    </valueHelp>
    <constraint>
      <regex>^(br|bond|dum|en|eth|gnv|peth|tun|vti|vxlan|wg|wlan)[0-9]+|lo$</regex>
    </constraint>
  </properties>
</leafNode>
<!-- included end -->
