<!-- include start from bgp/afi-route-map-export.xml.i -->
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
      #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
    </constraint>
    <constraintErrorMessage>Route map names can only contain alphanumeric characters, hyphens, and underscores</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
