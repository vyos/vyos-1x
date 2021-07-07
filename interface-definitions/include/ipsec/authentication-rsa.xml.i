<!-- include start from ipsec/authentication-rsa.xml.i -->
<node name="rsa">
  <properties>
    <help>RSA keys</help>
  </properties>
  <children>
    <leafNode name="local-key">
      <properties>
        <help>Name of PKI key-pair with local private key</help>
        <completionHelp>
          <path>pki key-pair</path>
        </completionHelp>
      </properties>
    </leafNode>
    <leafNode name="passphrase">
      <properties>
        <help>Local private key passphrase</help>
      </properties>
    </leafNode>
    <leafNode name="remote-key">
      <properties>
        <help>Name of PKI key-pair with remote public key</help>
        <completionHelp>
          <path>pki key-pair</path>
        </completionHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
