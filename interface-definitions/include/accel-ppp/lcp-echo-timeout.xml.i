<!-- include start from accel-ppp/lcp-echo-timeout.xml.i -->
<leafNode name="lcp-echo-timeout">
  <properties>
    <help>Timeout in seconds to wait for any peer activity. If this option specified it turns on adaptive lcp echo functionality and "lcp-echo-failure" is not used.</help>
    <constraint>
      <validator name="numeric" argument="--positive"/>
    </constraint>
  </properties>
  <defaultValue>0</defaultValue>
</leafNode>
<!-- include end -->
