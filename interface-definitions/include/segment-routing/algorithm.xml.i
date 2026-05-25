<!-- include start from segment-routing/algorithm.xml.i -->
<node name="algorithm">
  <properties>
    <help>IGP prefix algorithm style</help>
  </properties>
  <children>
    <leafNode name="spf">
      <properties>
        <help>Shortest Path First (SPF)</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="strict-spf">
      <properties>
        <help>Strict Shortest Path First (SPF) - ignore any possible local policy overriding the SPF along the path</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>