<!-- include start from constraint/host-name.xml.i -->
<valueHelp>
  <format>u32:1-200</format>
  <description>Policy route table number</description>
</valueHelp>
<constraint>
  <validator name="numeric" argument="--range 1-200"/>
</constraint>
<!-- include end -->
