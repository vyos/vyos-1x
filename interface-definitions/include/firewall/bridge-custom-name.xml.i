<!-- include start from firewall/bridge-custom-name.xml.i -->
<tagNode name="name">
  <properties>
    <help>Bridge custom firewall</help>
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
          <path>firewall bridge name</path>
        </completionHelp>
      </properties>
    </leafNode>
    <tagNode name="rule">
      <properties>
        <help>Bridge Firewall forward filter rule number</help>
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
      </children>
    </tagNode>
  </children>
</tagNode>
<!-- include end -->
