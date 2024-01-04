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
      #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
    </constraint>
    <constraintErrorMessage>Name of route-map can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
