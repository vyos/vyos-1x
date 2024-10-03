<!-- include start from firewall/ipv4-hook-forward.xml.i -->
<node name="forward">
  <properties>
    <help>IPv4 forward firewall</help>
  </properties>
  <children>
    <node name="filter">
      <properties>
        <help>IPv4 firewall forward filter</help>
      </properties>
      <children>
        #include <include/firewall/default-action-base-chains.xml.i>
        #include <include/firewall/default-log.xml.i>
        #include <include/generic-description.xml.i>
        <tagNode name="rule">
          <properties>
            <help>IPv4 Firewall forward filter rule number</help>
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
            #include <include/firewall/common-rule-ipv4.xml.i>
            #include <include/firewall/inbound-interface.xml.i>
            #include <include/firewall/match-ipsec.xml.i>
            #include <include/firewall/offload-target.xml.i>
            #include <include/firewall/outbound-interface.xml.i>
            #include <include/firewall/set-packet-modifications-dscp.xml.i>
            #include <include/firewall/set-packet-modifications-conn-mark.xml.i>
            #include <include/firewall/set-packet-modifications-mark.xml.i>
            #include <include/firewall/set-packet-modifications-tcp-mss.xml.i>
            #include <include/firewall/set-packet-modifications-ttl.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
