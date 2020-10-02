<!-- included start from accel-ppp-mppe.xml.i -->
<leafNode name="mppe">
  <properties>
    <help>Specifies mppe negotiation preferences</help>
    <completionHelp>
      <list>require prefer deny</list>
    </completionHelp>
    <constraint>
      <regex>(^require|prefer|deny)</regex>
    </constraint>
    <valueHelp>
      <format>require</format>
      <description>send mppe request, if client rejects, drop the connection</description>
    </valueHelp>
    <valueHelp>
      <format>prefer</format>
      <description>send mppe request, if client rejects continue</description>
    </valueHelp>
    <valueHelp>
      <format>deny</format>
      <description>drop all mppe</description>
    </valueHelp>
  </properties>
</leafNode>
<!-- included end -->
