<!-- include start from policy/community-value-list.xml.i -->
<valueHelp>
  <format>ASN:NN</format>
  <description>based on autonomous system number in format &lt;0-65535:0-4294967295&gt;</description>
</valueHelp>
<valueHelp>
  <format>IP:NN</format>
  <description>Based on a router-id IP address in format &lt;IP:0-65535&gt;</description>
</valueHelp>
<constraint>
  <validator name="bgp-extended-community"/>
</constraint>
<constraintErrorMessage>Should be in form: ASN:NN or IPADDR:NN where ASN is autonomous system number</constraintErrorMessage>
<multi/>
<!-- include end -->
