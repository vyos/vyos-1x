<!-- include start from bgp/neighbor-path-attribute.xml.i -->
<node name="path-attribute">
  <properties>
    <help>Manipulate path attributes from incoming UPDATE messages</help>
  </properties>
  <children>
    <leafNode name="discard">
      <properties>
        <help>Drop specified attributes from incoming UPDATE messages</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Attribute number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="treat-as-withdraw">
      <properties>
        <help>Treat-as-withdraw any incoming BGP UPDATE messages that contain the specified attribute</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Attribute number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
