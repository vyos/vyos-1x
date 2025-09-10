<!-- include start from isis/remote_lfa_tunnel.xml.i -->
<node name="tunnel">
  <properties>
    <help>Enable remote LFA computation using tunnels</help>
  </properties>
  <children>
    <leafNode name="mpls-ldp">
      <properties>
        <help>Use MPLS LDP tunnel to reach the remote LFA node</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->