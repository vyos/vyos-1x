<!-- include start from static/static-route6.xml.i -->
<tagNode name="route6">
  <properties>
    <help>Static IPv6 route</help>
    <valueHelp>
      <format>ipv6net</format>
      <description>IPv6 static route</description>
    </valueHelp>
    <constraint>
      <validator name="ipv6-prefix"/>
    </constraint>
  </properties>
  <children>
    #include <include/static/static-route-blackhole.xml.i>
    #include <include/static/static-route-reject.xml.i>
    #include <include/generic-description.xml.i>
    <tagNode name="interface">
      <properties>
        <help>IPv6 gateway interface name</help>
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
        #include <include/static/static-route-bfd.xml.i>
        #include <include/static/static-route-distance.xml.i>
        #include <include/static/static-route-interface.xml.i>
        #include <include/static/static-route-segments.xml.i>
        #include <include/static/static-route-vrf.xml.i>
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- include end -->
