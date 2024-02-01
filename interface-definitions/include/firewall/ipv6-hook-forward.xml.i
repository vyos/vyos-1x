<!-- include start from firewall/ipv6-hook-forward.xml.i -->
<node name="forward">
  <properties>
    <help>IPv6 forward firewall</help>
  </properties>
  <children>
    <node name="filter">
      <properties>
        <help>IPv6 firewall forward filter</help>
      </properties>
      <children>
        #include <include/firewall/default-action-base-chains.xml.i>
        #include <include/firewall/default-log.xml.i>
        #include <include/generic-description.xml.i>
        <tagNode name="rule">
          <properties>
            <help>IPv6 Firewall forward filter rule number</help>
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
            #include <include/firewall/action-forward.xml.i>
            #include <include/firewall/common-rule-ipv6.xml.i>
            #include <include/firewall/inbound-interface.xml.i>
            #include <include/firewall/match-ipsec.xml.i>
            #include <include/firewall/offload-target.xml.i>
            #include <include/firewall/outbound-interface.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
