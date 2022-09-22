<!-- include start from firewall/tcp-flags.xml.i -->
<node name="tcp">
  <properties>
    <help>TCP flags to match</help>
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
    <leafNode name="mss">
      <properties>
        <help>Maximum segment size (MSS)</help>
        <valueHelp>
          <format>u32:1-16384</format>
          <description>Maximum segment size</description>
        </valueHelp>
        <valueHelp>
          <format>&lt;min&gt;-&lt;max&gt;</format>
          <description>TCP MSS range (use '-' as delimiter)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--allow-range --range 1-16384"/>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
