<!-- include start from bgp/afi-route-map.xml.i -->
<leafNode name="export">
  <properties>
    <help>Route-map to filter outgoing route updates</help>
    <completionHelp>
      <path>policy route-map</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Route map name</description>
    </valueHelp>
    <constraint>
      <regex>[-_a-zA-Z0-9.]+</regex>
    </constraint>
    <constraintErrorMessage>Name of route-map can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
  </properties>
</leafNode>
<leafNode name="import">
  <properties>
    <help>Route-map to filter incoming route updates</help>
    <completionHelp>
      <path>policy route-map</path>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Route map name</description>
    </valueHelp>
    <constraint>
      <regex>[-_a-zA-Z0-9.]+</regex>
    </constraint>
    <constraintErrorMessage>Name of route-map can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
