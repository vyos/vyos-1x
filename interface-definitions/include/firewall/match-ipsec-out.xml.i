<!-- include start from firewall/match-ipsec-out.xml.i -->
<node name="ipsec">
  <properties>
    <help>Outbound IPsec packets</help>
  </properties>
  <children>
    <leafNode name="match-ipsec-out">
      <properties>
        <help>Outbound traffic to be IPsec encapsulated</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="match-none-out">
      <properties>
        <help>Outbound traffic that will not be IPsec encapsulated</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->