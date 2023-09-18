<!-- include start from firewall/tcp-flags.xml.i -->
<node name="tcp">
  <properties>
    <help>TCP options to match</help>
  </properties>
  <children>
    <node name="flags">
      <properties>
        <help>TCP flags to match</help>
      </properties>
      <children>
        <leafNode name="syn">
          <properties>
            <help>Synchronise flag</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="ack">
          <properties>
            <help>Acknowledge flag</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="fin">
          <properties>
            <help>Finish flag</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="rst">
          <properties>
            <help>Reset flag</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="urg">
          <properties>
            <help>Urgent flag</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="psh">
          <properties>
            <help>Push flag</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="ecn">
          <properties>
            <help>Explicit Congestion Notification flag</help>
            <valueless/>
          </properties>
        </leafNode>
        <leafNode name="cwr">
          <properties>
            <help>Congestion Window Reduced flag</help>
            <valueless/>
          </properties>
        </leafNode>
        <node name="not">
          <properties>
            <help>Match flags not set</help>
          </properties>
          <children>
            <leafNode name="syn">
              <properties>
                <help>Synchronise flag</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="ack">
              <properties>
                <help>Acknowledge flag</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="fin">
              <properties>
                <help>Finish flag</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="rst">
              <properties>
                <help>Reset flag</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="urg">
              <properties>
                <help>Urgent flag</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="psh">
              <properties>
                <help>Push flag</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="ecn">
              <properties>
                <help>Explicit Congestion Notification flag</help>
                <valueless/>
              </properties>
            </leafNode>
            <leafNode name="cwr">
              <properties>
                <help>Congestion Window Reduced flag</help>
                <valueless/>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
