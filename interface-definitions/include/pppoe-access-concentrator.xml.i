<!-- include start from pppoe-access-concentrator.xml.i -->
<leafNode name="access-concentrator">
  <properties>
    <help>Access concentrator name</help>
    <constraint>
      <regex>[a-zA-Z0-9]{1,100}</regex>
    </constraint>
    <constraintErrorMessage>Access-concentrator name must be alphanumerical only (max. 100 characters)</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
