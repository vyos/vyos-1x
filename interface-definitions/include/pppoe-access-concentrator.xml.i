<!-- include start from pppoe-access-concentrator.xml.i -->
<leafNode name="access-concentrator">
  <properties>
    <help>Access concentrator name</help>
    <constraint>
       #include <include/constraint/alpha-numeric-hyphen-underscore.xml.i>
    </constraint>
    <constraintErrorMessage>Access-concentrator name can only contain alpha-numeric letters, hyphen and underscores(max. 100 characters)</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
