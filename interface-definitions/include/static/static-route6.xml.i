<!-- include start from static/static-route6.xml.i -->
<tagNode name="route6">
  <properties>
    <help>VRF static IPv6 route</help>
    <valueHelp>
      <format>ipv6net</format>
      <description>IPv6 static route</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6-prefix"/>
    </constraint>
  </properties>
  <children>
    <node name="blackhole">
      <properties>
        <help>Silently discard pkts when matched</help>
      </properties>
      <children>
        #include <include/static/static-route-distance.xml.i>
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
        <help>IPv6 gateway interface name</help>
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
        #include <include/static/static-route-distance.xml.i>
        #include <include/static/static-route-vrf.xml.i>
      </children>
    </tagNode>
    <tagNode name="next-hop">
      <properties>
        <help>IPv6 gateway address</help>
        <valueHelp>
          <format>ipv6</format>
          <description>Next-hop IPv6 router</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-address"/>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/static/static-route-distance.xml.i>
        #include <include/static/static-route-interface.xml.i>
        #include <include/static/static-route-vrf.xml.i>
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- include end -->

