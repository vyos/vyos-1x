<!-- include start from rip/access-list.xml.i -->
<node name="access-list">
  <properties>
    <help>Access-list</help>
  </properties>
  <children>
    <leafNode name="in">
      <properties>
        <help>Access list to apply to input packets</help>
        <valueHelp>
          <format>u32</format>
          <description>Access list to apply to input packets</description>
        </valueHelp>
        <completionHelp>
          <path>policy access-list</path>
        </completionHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="out">
      <properties>
        <help>Access list to apply to output packets</help>
        <valueHelp>
          <format>u32</format>
          <description>Access list to apply to output packets</description>
        </valueHelp>
        <completionHelp>
          <path>policy access-list</path>
        </completionHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-4294967295"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
