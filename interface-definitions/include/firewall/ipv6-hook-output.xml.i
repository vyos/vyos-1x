<!-- include start from firewall/ipv6-hook-output.xml.i -->
<node name="output">
  <properties>
    <help>IPv6 output firewall</help>
  </properties>
  <children>
    <node name="filter">
      <properties>
        <help>IPv6 firewall output filter</help>
      </properties>
      <children>
        #include <include/firewall/default-action-base-chains.xml.i>
        #include <include/firewall/default-log.xml.i>
        #include <include/generic-description.xml.i>
        <tagNode name="rule">
          <properties>
            <help>IPv6 Firewall output filter rule number</help>
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
            #include <include/firewall/common-rule-ipv6.xml.i>
            #include <include/firewall/match-ipsec-out.xml.i>
            #include <include/firewall/outbound-interface.xml.i>
            #include <include/firewall/set-packet-modifications-dscp.xml.i>
            #include <include/firewall/set-packet-modifications-conn-mark.xml.i>
            #include <include/firewall/set-packet-modifications-mark.xml.i>
            #include <include/firewall/set-packet-modifications-tcp-mss.xml.i>
            #include <include/firewall/set-packet-modifications-hop-limit.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
        <node name="raw">
      <properties>
        <help>IPv6 firewall output raw</help>
      </properties>
      <children>
        #include <include/firewall/default-action-base-chains.xml.i>
        #include <include/firewall/default-log.xml.i>
        #include <include/generic-description.xml.i>
        <tagNode name="rule">
          <properties>
            <help>IPv6 Firewall output raw rule number</help>
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
            #include <include/firewall/match-ipsec-out.xml.i>
            #include <include/firewall/outbound-interface.xml.i>
            #include <include/firewall/set-packet-modifications-dscp.xml.i>
            #include <include/firewall/set-packet-modifications-conn-mark.xml.i>
            #include <include/firewall/set-packet-modifications-mark.xml.i>
            #include <include/firewall/set-packet-modifications-tcp-mss.xml.i>
            #include <include/firewall/set-packet-modifications-hop-limit.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
