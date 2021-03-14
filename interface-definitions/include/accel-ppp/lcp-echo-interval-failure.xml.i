<!-- include start from accel-ppp/lcp-echo-interval-failure.xml.i -->
<leafNode name="lcp-echo-interval">
  <properties>
    <help>LCP echo-requests/sec</help>
    <constraint>
      <validator name="numeric" argument="--positive"/>
    </constraint>
  </properties>
  <defaultValue>30</defaultValue>
</leafNode>
<leafNode name="lcp-echo-failure">
  <properties>
    <help>Maximum number of Echo-Requests may be sent without valid reply</help>
    <constraint>
      <validator name="numeric" argument="--positive"/>
    </constraint>
  </properties>
  <defaultValue>3</defaultValue>
</leafNode>
<!-- include end -->
