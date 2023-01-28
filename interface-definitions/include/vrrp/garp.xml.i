<!-- include start from vrrp/garp.xml.i -->
<node name="garp">
  <properties>
    <help>Gratuitous ARP parameters</help>
  </properties>
  <children>
    <leafNode name="interval">
      <properties>
        <help>Interval between Gratuitous ARP</help>
        <valueHelp>
          <format>&lt;0.000-1000&gt;</format>
          <description>Interval in seconds, resolution microseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0.000-1000 --float"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
    <leafNode name="master-delay">
      <properties>
        <help>Delay for second set of gratuitous ARPs after transition to master</help>
        <valueHelp>
          <format>u32:1-1000</format>
          <description>Delay in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-1000"/>
        </constraint>
      </properties>
      <defaultValue>5</defaultValue>
    </leafNode>
    <leafNode name="master-refresh">
      <properties>
        <help>Minimum time interval for refreshing gratuitous ARPs while beeing master</help>
        <valueHelp>
          <format>u32:0</format>
          <description>No refresh</description>
        </valueHelp>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Interval in seconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>5</defaultValue>
    </leafNode>
    <leafNode name="master-refresh-repeat">
      <properties>
        <help>Number of gratuitous ARP messages to send at a time while beeing master</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Number of gratuitous ARP messages</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>1</defaultValue>
    </leafNode>
    <leafNode name="master-repeat">
      <properties>
        <help>Number of gratuitous ARP messages to send at a time after transition to master</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Number of gratuitous ARP messages</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>5</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
