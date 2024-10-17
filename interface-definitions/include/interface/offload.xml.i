<!-- include start from interface/offload.xml.i -->
<node name="offload">
  <properties>
    <help>Configurable offload options</help>
  </properties>
  <children>
    <leafNode name="gro">
      <properties>
        <help>Enable Generic Receive Offload</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="gso">
      <properties>
        <help>Enable Generic Segmentation Offload</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="hw-tc-offload">
      <properties>
        <help>Enable Hardware Flow Offload</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="lro">
      <properties>
        <help>Enable Large Receive Offload</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="rps">
      <properties>
        <help>Enable Receive Packet Steering</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="rfs">
      <properties>
        <help>Enable Receive Flow Steering</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="sg">
      <properties>
        <help>Enable Scatter-Gather</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="tso">
      <properties>
        <help>Enable TCP Segmentation Offloading</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
