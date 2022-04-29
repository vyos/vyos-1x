<!-- include start from accel-ppp/ppp-mppe.xml.i -->
<leafNode name="mppe">
  <properties>
    <help>Specifies mppe negotiation preferences</help>
    <completionHelp>
      <list>require prefer deny</list>
    </completionHelp>
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
    <constraint>
      <regex>(require|prefer|deny)</regex>
    </constraint>
  </properties>
  <defaultValue>prefer</defaultValue>
</leafNode>
<!-- include end -->
