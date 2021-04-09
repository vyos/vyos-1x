<!-- include start from route-map.xml.i -->
<leafNode name="route-map">
  <properties>
    <help>Specify route-map name to use</help>
    <completionHelp>
      <path>policy route-map</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Route map name</description>
    </valueHelp>
    <constraint>
      <regex>^[-a-zA-Z0-9.]+$</regex>
    </constraint>
    <constraintErrorMessage>Route-map name can only contain alpha-numeric letters and a hyphen</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
