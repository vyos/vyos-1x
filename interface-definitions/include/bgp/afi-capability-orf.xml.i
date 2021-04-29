<!-- include start from bgp/afi-capability-orf.xml.i -->
<node name="orf">
  <properties>
    <help>Advertise ORF capability to this peer</help>
  </properties>
  <children>
    <node name="prefix-list">
      <properties>
        <help>Advertise prefix-list ORF capability to this peer</help>
      </properties>
      <children>
        <leafNode name="receive">
          <properties>
            <help>Capability to receive the ORF</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="send">
          <properties>
            <help>Capability to send the ORF</help>
            <valueless/>
          </properties>
        </leafNode>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
