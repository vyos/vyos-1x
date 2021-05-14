<!-- include start from bgp/afi-ipv6-prefix-list.xml.i -->
<node name="prefix-list">
  <properties>
    <help>Prefix-list to filter route updates to/from this peer</help>
  </properties>
  <children>
    <leafNode name="export">
      <properties>
        <help>Prefix-list to filter outgoing route updates to this peer</help>
        <completionHelp>
          <path>policy prefix-list6</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Name of IPv6 prefix-list</description>
        </valueHelp>
        <constraint>
          <regex>^[-_a-zA-Z0-9]+$</regex>
        </constraint>
        <constraintErrorMessage>Name of prefix-list6 can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
      </properties>
    </leafNode>
    <leafNode name="import">
      <properties>
        <help>Prefix-list to filter incoming route updates from this peer</help>
        <completionHelp>
          <path>policy prefix-list6</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Name of IPv6 prefix-list</description>
        </valueHelp>
        <constraint>
          <regex>^[-_a-zA-Z0-9]+$</regex>
        </constraint>
        <constraintErrorMessage>Name of prefix-list6 can only contain alpha-numeric letters, hyphen and underscores</constraintErrorMessage>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
