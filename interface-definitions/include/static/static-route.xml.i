<!-- include start from static/static-route.xml.i -->
<tagNode name="route">
  <properties>
    <help>Static IPv4 route</help>
    <valueHelp>
      <format>ipv4net</format>
      <description>IPv4 static route</description>
    </valueHelp>
    <constraint>
      <validator name="ipv4-prefix"/>
    </constraint>
  </properties>
  <children>
    #include <include/static/static-route-blackhole.xml.i>
    #include <include/static/static-route-reject.xml.i>
    #include <include/dhcp-interface-multi.xml.i>
    #include <include/generic-description.xml.i>
    <tagNode name="interface">
      <properties>
        <help>Next-hop IPv4 router interface</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces</script>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Gateway interface name</description>
        </valueHelp>
        <constraint>
          #include <include/constraint/interface-name.xml.i>
        </constraint>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        #include <include/static/static-route-distance.xml.i>
        #include <include/static/static-route-segments.xml.i>
        #include <include/static/static-route-vrf.xml.i>
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
        #include <include/static/static-route-distance.xml.i>
        #include <include/generic-interface.xml.i>
        #include <include/static/static-route-segments.xml.i>
        #include <include/static/static-route-vrf.xml.i>
        <node name="bfd">
          <properties>
            <help>BFD monitoring</help>
          </properties>
          <children>
            #include <include/bfd/profile.xml.i>
            <node name="multi-hop">
              <properties>
                <help>Configure BFD multi-hop session</help>
              </properties>
              <children>
                #include <include/source-address-ipv4.xml.i>
              </children>
            </node>
          </children>
        </node>
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- include end -->
