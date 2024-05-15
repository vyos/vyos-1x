<!-- include start from firewall/ipv6-hook-prerouting.xml.i -->
<node name="prerouting">
  <properties>
    <help>IPv6 prerouting firewall</help>
  </properties>
  <children>
    <node name="raw">
      <properties>
        <help>IPv6 firewall prerouting raw</help>
      </properties>
      <children>
        #include <include/firewall/default-action-base-chains.xml.i>
        #include <include/generic-description.xml.i>
        <leafNode name="default-jump-target">
          <properties>
            <help>Set jump target. Action jump must be defined in default-action to use this setting</help>
            <completionHelp>
              <path>firewall ipv6 name</path>
            </completionHelp>
          </properties>
        </leafNode>
        <tagNode name="rule">
          <properties>
            <help>IPv6 Firewall prerouting raw rule number</help>
            <valueHelp>
              <format>u32:1-999999</format>
              <description>Number for this firewall rule</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 1-999999"/>
            </constraint>
            <constraintErrorMessage>Firewall rule number must be between 1 and 999999</constraintErrorMessage>
          </properties>
          <children>
            #include <include/firewall/common-rule-ipv6-raw.xml.i>
            #include <include/firewall/inbound-interface.xml.i>
            <leafNode name="jump-target">
              <properties>
                <help>Set jump target. Action jump must be defined to use this setting</help>
                <completionHelp>
                  <path>firewall ipv6 name</path>
                </completionHelp>
              </properties>
            </leafNode>
          </children>
        </tagNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->