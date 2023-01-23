<!-- include start from vrrp/garp.xml.i -->
<node name="garp">
  <properties>
    <help>Gratuitous ARP parameters</help>
  </properties>
  <children>
    <leafNode name="master-delay">
      <properties>
        <help>Delay for second set of gratuitous ARPs after transition to MASTER</help>
        <valueHelp>
          <format>u32:1-1000</format>
          <description>Delay for second set of gratuitous ARPs after transition to MASTER</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-1000"/>
        </constraint>
      </properties>
      <defaultValue>5</defaultValue>
    </leafNode>
    <leafNode name="master-repeat">
      <properties>
        <help>Number of gratuitous ARP messages to send at a time after transition to MASTER</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Number of gratuitous ARP messages to send at a time after transition to MASTER</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>5</defaultValue>
    </leafNode>
    <leafNode name="master-refresh">
      <properties>
        <help>Minimum time interval for refreshing gratuitous ARPs while MASTER. 0 means no refresh</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Minimum time interval for refreshing gratuitous ARPs while MASTER. 0 means no refresh</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>5</defaultValue>
    </leafNode>
    <leafNode name="master-refresh-repeat">
      <properties>
        <help>Number of gratuitous ARP messages to send at a time while MASTER</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>Number of gratuitous ARP messages to send at a time while MASTER</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>1</defaultValue>
    </leafNode>
    <leafNode name="interval">
      <properties>
        <help>Delay between gratuitous ARP messages sent on an interface</help>
        <valueHelp>
          <format>&lt;0.000-1000&gt;</format>
          <description>Delay between gratuitous ARP messages sent on an interface</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0.000-1000 --float"/>
        </constraint>
      </properties>
      <defaultValue>0</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
