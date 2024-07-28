<!-- include start from firewall/match-ipsec.xml.i -->
<node name="ipsec">
  <properties>
    <help>IPsec encapsulated packets</help>
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