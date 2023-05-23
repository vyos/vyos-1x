<!-- include start from firewall/ipv4-hook-input.xml.i -->
<node name="input">
  <properties>
    <help>IPv4 input firewall</help>
  </properties>
  <children>
    <node name="filter">
      <properties>
        <help>IPv4 firewall input filter</help>
      </properties>
      <children>
        #include <include/firewall/default-action-base-chains.xml.i>
        #include <include/generic-description.xml.i>
        <tagNode name="rule">
          <properties>
            <help>IP Firewall input filter rule number</help>
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
            #include <include/firewall/common-rule-ipv4.xml.i>
            #include <include/firewall/inbound-interface.xml.i>
            <leafNode name="jump-target">
              <properties>
                <help>Set jump target. Action jump must be defined to use this setting</help>
                <completionHelp>
                  <path>firewall ip name</path>
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