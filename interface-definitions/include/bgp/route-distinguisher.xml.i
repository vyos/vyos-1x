<!-- include start from bgp/route-distinguisher.xml.i -->
<leafNode name="rd">
  <properties>
    <help>Route Distinguisher</help>
    <valueHelp>
      <format>ASN:NN_OR_IP-ADDRESS:NN</format>
      <description>Route Distinguisher, (x.x.x.x:yyy|xxxx:yyyy)</description>
    </valueHelp>
    <constraint>
      <regex>^((25[0-5]|2[0-4][0-9]|[1][0-9][0-9]|[1-9][0-9]|[0-9]?)(\.(25[0-5]|2[0-4][0-9]|[1][0-9][0-9]|[1-9][0-9]|[0-9]?)){3}|[0-9]{1,10}):[0-9]{1,5}$</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
