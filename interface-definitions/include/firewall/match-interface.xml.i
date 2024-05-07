<!-- include start from firewall/match-interface.xml.i -->
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
      <regex>(\!?)(bond|br|dum|en|ersp|eth|gnv|ifb|ipoe|lan|l2tp|l2tpeth|macsec|peth|ppp|pppoe|pptp|sstp|tun|veth|vti|vtun|vxlan|wg|wlan|wwan)([0-9]?)(\*?)(.+)?|(\!?)lo</regex>
      <validator name="vrf-name"/>
    </constraint>
  </properties>
</leafNode>
<leafNode name="group">
  <properties>
    <help>Match interface-group</help>
    <completionHelp>
      <path>firewall group interface-group</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface-group name to match</description>
    </valueHelp>
    <valueHelp>
      <format>!txt</format>
      <description>Inverted interface-group name to match</description>
    </valueHelp>
  </properties>
</leafNode>
<!-- include end -->