<!-- include start from bgp/route-target-export.xml.i -->
<leafNode name="export">
  <properties>
    <help>Route Target export</help>
    <valueHelp>
      <format>txt</format>
      <description>Route target (x.x.x.x:yyy|xxxx:yyyy)</description>
    </valueHelp>
    <constraint>
      <regex>^((25[0-5]|2[0-4][0-9]|[1][0-9][0-9]|[1-9][0-9]|[0-9]?)(\.(25[0-5]|2[0-4][0-9]|[1][0-9][0-9]|[1-9][0-9]|[0-9]?)){3}|[0-9]{1,10}):[0-9]{1,5}$</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
