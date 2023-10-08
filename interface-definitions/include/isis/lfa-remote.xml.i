<!-- include start from isis/lfa-remote.xml.i -->
<node name="remote">
  <properties>
    <help>Remote loop free alternate options</help>
  </properties>
  <children>
    <tagNode name="prefix-list">
      <properties>
        <help>Filter PQ node router ID based on prefix list</help>
        <completionHelp>
          <path>policy prefix-list</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Name of IPv4/IPv6 prefix-list</description>
        </valueHelp>
        <constraint>
          #include <include/constraint/alpha-numeric-hyphen-underscore.xml.i>
        </constraint>
        <constraintErrorMessage>Name of prefix-list can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
      </properties>
      <children>
        #include <include/isis/level-1-2-leaf.xml.i>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->