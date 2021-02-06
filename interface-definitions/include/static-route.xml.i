<!-- included start from static-route.xml.i -->
<tagNode name="route">
  <properties>
    <help>VRF static IPv4 route</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 static route</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-prefix"/>
    </constraint>
  </properties>
  <children>
    <node name="blackhole">
      <properties>
        <help>Silently discard pkts when matched</help>
      </properties>
      <children>
        #include <include/static-route-distance.xml.i>
        <leafNode name="tag">
          <properties>
            <help>Tag value for this route</help>
            <valueHelp>
              <format>u32:1-4294967295</format>
              <description>Tag value for this route</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-4294967295"/>
            </constraint>
          </properties>
        </leafNode>
      </children>
    </node>
    <tagNode name="interface">
      <properties>
        <help>Next-hop IPv4 router interface</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces.py</script>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Gateway interface name</description>
        </valueHelp>
        <constraint>
          <validator name="interface-name"/>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/static-route-distance.xml.i>
        #include <include/static-route-vrf.xml.i>
      </children>
    </tagNode>
    <tagNode name="next-hop">
      <properties>
        <help>Next-hop IPv4 router address</help>
        <valueHelp>
          <format>ipv4</format>
          <description>Next-hop router address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-address"/>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/static-route-distance.xml.i>
        #include <include/static-route-interface.xml.i>
        #include <include/static-route-vrf.xml.i>
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- included end -->

