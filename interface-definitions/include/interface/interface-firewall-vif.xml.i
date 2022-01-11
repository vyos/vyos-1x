<!-- include start from interface/interface-firewall-vif.xml.i -->
<node name="firewall" owner="${vyos_conf_scripts_dir}/firewall-interface.py $VAR(../../@).$VAR(../@)">
  <properties>
    <priority>615</priority>
    <help>Firewall options</help>
  </properties>
  <children>
    <node name="in">
      <properties>
        <help>forwarded packets on inbound interface</help>
      </properties>
      <children>
        <leafNode name="name">
          <properties>
            <help>Inbound IPv4 firewall ruleset name for interface</help>
            <completionHelp>
              <path>firewall name</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="ipv6-name">
          <properties>
            <help>Inbound IPv6 firewall ruleset name for interface</help>
            <completionHelp>
              <path>firewall ipv6-name</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="out">
      <properties>
        <help>forwarded packets on outbound interface</help>
      </properties>
      <children>
        <leafNode name="name">
          <properties>
            <help>Outbound IPv4 firewall ruleset name for interface</help>
            <completionHelp>
              <path>firewall name</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="ipv6-name">
          <properties>
            <help>Outbound IPv6 firewall ruleset name for interface</help>
            <completionHelp>
              <path>firewall ipv6-name</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="local">
      <properties>
        <help>packets destined for this router</help>
      </properties>
      <children>
        <leafNode name="name">
          <properties>
            <help>Local IPv4 firewall ruleset name for interface</help>
            <completionHelp>
              <path>firewall name</path>
            </completionHelp>
          </properties>
        </leafNode>
        <leafNode name="ipv6-name">
          <properties>
            <help>Local IPv6 firewall ruleset name for interface</help>
            <completionHelp>
              <path>firewall ipv6-name</path>
            </completionHelp>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
