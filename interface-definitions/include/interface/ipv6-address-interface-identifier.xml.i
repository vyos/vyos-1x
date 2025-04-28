<!-- include start from interface/ipv6-address-interface-identifier.xml.i -->
<leafNode name="interface-identifier">
  <properties>
    <help>SLAAC interface identifier</help>
    <valueHelp>
      <format>::h:h:h:h</format>
      <description>Interface identifier</description>
    </valueHelp>
    <constraint>
      <regex>::([0-9a-fA-F]{1,4}(:[0-9a-fA-F]{1,4}){0,3})</regex>
    </constraint>
    <constraintErrorMessage>Interface identifier format must start with :: and may contain up four hextets (::h:h:h:h)</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
