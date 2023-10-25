<!-- include start from firewall/inbound-interface-no-group.xml.i -->
<node name="inbound-interface">
  <properties>
    <help>Match inbound-interface</help>
  </properties>
  <children>
    <leafNode name="name">
      <properties>
        <help>Match interface</help>
        <completionHelp>
          <script>${vyos_completion_dir}/list_interfaces</script>
          <path>vrf name</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Interface name</description>
        </valueHelp>
        <valueHelp>
          <format>txt*</format>
          <description>Interface name with wildcard</description>
        </valueHelp>
        <valueHelp>
          <format>!txt</format>
          <description>Inverted interface name to match</description>
        </valueHelp>
        <constraint>
          <regex>(\!?)(bond|br|dum|en|ersp|eth|gnv|ifb|lan|l2tp|l2tpeth|macsec|peth|ppp|pppoe|pptp|sstp|tun|veth|vti|vtun|vxlan|wg|wlan|wwan)([0-9]?)(\*?)(.+)?|(\!?)lo</regex>
          <validator name="vrf-name"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->