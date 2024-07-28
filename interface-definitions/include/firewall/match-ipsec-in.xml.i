<!-- include start from firewall/match-ipsec-in.xml.i -->
<node name="ipsec">
  <properties>
    <help>Inbound IPsec packets</help>
  </properties>
  <children>
    <leafNode name="match-ipsec-in">
      <properties>
        <help>Inbound traffic that was IPsec encapsulated</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="match-none-in">
      <properties>
        <help>Inbound traffic that was not IPsec encapsulated</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->