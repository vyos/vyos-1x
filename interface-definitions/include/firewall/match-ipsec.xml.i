<!-- include start from firewall/match-ipsec.xml.i -->
<node name="ipsec">
  <properties>
    <help>Inbound IPsec packets</help>
  </properties>
  <children>
    <leafNode name="match-ipsec">
      <properties>
        <help>Inbound IPsec packets</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="match-none">
      <properties>
        <help>Inbound non-IPsec packets</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->