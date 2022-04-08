<!-- include start from qos/tcp-flags.xml.i -->
<node name="tcp">
  <properties>
    <help>TCP Flags matching</help>
  </properties>
  <children>
    <leafNode name="ack">
      <properties>
        <help>Match TCP ACK</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="syn">
      <properties>
        <help>Match TCP SYN</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
