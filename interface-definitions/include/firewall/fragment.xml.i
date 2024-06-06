<!-- include start from firewall/fragment.xml.i -->
<node name="fragment">
  <properties>
    <help>IP fragment match</help>
  </properties>
  <children>
    <leafNode name="match-frag">
      <properties>
        <help>Second and further fragments of fragmented packets</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="match-non-frag">
      <properties>
        <help>Head fragments or unfragmented packets</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->