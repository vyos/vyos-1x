<!-- include start from nat-flags.xml.i -->
<node name="nat-flags">
  <properties>
    <help>NAT Rule flags</help>
  </properties>
  <children>
    <leafNode name="persistent">
      <properties>
        <help>Gives a client the same source or destination-address for each connection</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="fully-random">
      <properties>
        <help>Full port randomization</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="random">
      <properties>
        <help>Randomize source port mapping</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
