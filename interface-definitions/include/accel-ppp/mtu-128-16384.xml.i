<!-- include start from accel-ppp/mtu-128-16384.xml.i -->
<leafNode name="mtu">
  <properties>
    <help>Maximum Transmission Unit (MTU)</help>
    <constraint>
      <validator name="numeric" argument="--range 128-16384"/>
    </constraint>
  </properties>
  <defaultValue>1492</defaultValue>
</leafNode>
<!-- include end -->
