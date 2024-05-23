<!-- include start from nat-translation-options.xml.i -->
<node name="options">
  <properties>
    <help>Translation options</help>
  </properties>
  <children>
    <leafNode name="address-mapping">
      <properties>
        <help>Address mapping options</help>
        <completionHelp>
          <list>persistent random</list>
        </completionHelp>
        <valueHelp>
          <format>persistent</format>
          <description>Gives a client the same source or destination-address for each connection</description>
        </valueHelp>
        <valueHelp>
          <format>random</format>
          <description>Random source or destination address allocation for each connection</description>
        </valueHelp>
        <constraint>
          <regex>(persistent|random)</regex>
        </constraint>
      </properties>
      <defaultValue>random</defaultValue>
    </leafNode>
    <leafNode name="port-mapping">
      <properties>
        <help>Port mapping options</help>
        <completionHelp>
          <list>random none</list>
        </completionHelp>
        <valueHelp>
          <format>random</format>
          <description>Randomize source port mapping</description>
        </valueHelp>
        <valueHelp>
          <format>none</format>
          <description>Do not apply port randomization</description>
        </valueHelp>
        <constraint>
          <regex>(random|none)</regex>
        </constraint>
      </properties>
      <defaultValue>none</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
