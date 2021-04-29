<!-- include start from nat-flags.xml.i -->
<leafNode name="nat-flags">
  <properties>
    <help>NAT Rule flags</help>
  </properties>
  <children>
    <leafNode name="persistent">
      <properties>
        <help>Gives a client the same source-/destination-address for each connection</help>
      </properties>
      <valueless/>
    </leafNode>
    <leafNode name="fully-random">
      <properties>
        <help>Full port randomization</help>
      </properties>
      <valueless/>
    </leafNode>
    <leafNode name="random">
      <properties>
        <help>Randomize source port mapping</help>
      </properties>
      <valueless/>
    </leafNode>
  </children>
</leafNode>
<!-- include end -->
