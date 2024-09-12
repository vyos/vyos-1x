<!-- include start from net.xml.i -->
<leafNode name="net">
  <properties>
    <help>A Network Entity Title for the process (ISO only)</help>
    <valueHelp>
      <format>XX.XXXX. ... .XXX.XX</format>
      <description>Network entity title (NET)</description>
    </valueHelp>
    <constraint>
      <regex>[a-fA-F0-9]{2}(\.[a-fA-F0-9]{4}){3,9}\.[a-fA-F0-9]{2}</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
