<!-- include start from vpp/acl_common_interface_ip_rule.xml.i -->
<tagNode name="acl-tag">
  <properties>
    <help>ACL rule (tag) number</help>
    <valueHelp>
      <format>u32</format>
      <description>Number</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 1-4294967295"/>
    </constraint>
    <constraintErrorMessage>Number must be between 1 and 4294967295</constraintErrorMessage>
  </properties>
  <children>
    <leafNode name="tag-name">
      <properties>
        <help>ACL tag name</help>
        <completionHelp>
          <path>vpp acl ip tag-name</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
