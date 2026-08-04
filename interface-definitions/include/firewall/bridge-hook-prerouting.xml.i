<!-- include start from firewall/bridge-hook-prerouting.xml.i -->
<node name="prerouting">
  <properties>
    <help>Bridge prerouting firewall</help>
  </properties>
  <children>
    <node name="filter">
      <properties>
        <help>Bridge firewall prerouting filter</help>
      </properties>
      <children>
        #include <include/firewall/default-action-base-chains.xml.i>
        #include <include/firewall/default-log.xml.i>
        #include <include/generic-description.xml.i>
        <tagNode name="rule">
          <properties>
            <help>Bridge firewall prerouting filter rule number</help>
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
            #include <include/firewall/common-rule-bridge.xml.i>
            #include <include/firewall/action-and-notrack.xml.i>
            #include <include/firewall/inbound-interface.xml.i>
            #include <include/firewall/set-packet-modifications-dscp.xml.i>
            #include <include/firewall/set-packet-modifications-mark.xml.i>
            #include <include/firewall/set-packet-modifications-tcp-mss.xml.i>
            #include <include/firewall/set-packet-modifications-ttl.xml.i>
            #include <include/firewall/set-packet-modifications-hop-limit.xml.i>
          </children>
        </tagNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
