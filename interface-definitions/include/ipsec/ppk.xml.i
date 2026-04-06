<!-- include start from ipsec/ppk.xml.i -->
<node name="ppk">
  <properties>
    <help>Post-quantum preshared key</help>
  </properties>
  <children>
    <leafNode name="id">
      <properties>
        <help>Post-quantum preshared key for this connection</help>
        <valueHelp>
          <format>txt</format>
          <description>ID used for PPK</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="required">
      <properties>
        <help>Require a valid PPK for connection to establish</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
