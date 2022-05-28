<!-- include start from rip/prefix-list.xml.i -->
<node name="prefix-list">
  <properties>
    <help>Prefix-list</help>
  </properties>
  <children>
    <leafNode name="in">
      <properties>
        <help>Prefix-list to apply to input packets</help>
        <valueHelp>
          <format>txt</format>
          <description>Prefix-list to apply to input packets</description>
        </valueHelp>
        <completionHelp>
          <path>policy prefix-list6</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="out">
      <properties>
        <help>Prefix-list to apply to output packets</help>
        <valueHelp>
          <format>txt</format>
          <description>Prefix-list to apply to output packets</description>
        </valueHelp>
        <completionHelp>
          <path>policy prefix-list6</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
