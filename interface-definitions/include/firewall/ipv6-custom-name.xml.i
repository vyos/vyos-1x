<!-- include start from firewall/ipv6-custom-name.xml.i -->
<tagNode name="name">
  <properties>
    <help>IPv6 custom firewall</help>
    <constraint>
      <regex>[a-zA-Z0-9][\w\-\.]*</regex>
    </constraint>
  </properties>
  <children>
    #include <include/firewall/default-action.xml.i>
    #include <include/firewall/default-log.xml.i>
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
        <help>IPv6 Firewall custom rule number</help>
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
        #include <include/firewall/inbound-interface.xml.i>
        #include <include/firewall/match-ipsec.xml.i>
        #include <include/firewall/offload-target.xml.i>
        #include <include/firewall/outbound-interface.xml.i>
        #include <include/firewall/set-packet-modifications-dscp.xml.i>
        #include <include/firewall/set-packet-modifications-conn-mark.xml.i>
        #include <include/firewall/set-packet-modifications-mark.xml.i>
        #include <include/firewall/set-packet-modifications-tcp-mss.xml.i>
        #include <include/firewall/set-packet-modifications-hop-limit.xml.i>
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- include end -->
