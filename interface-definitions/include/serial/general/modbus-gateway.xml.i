<!-- include start from serial/general/modbus-gateway.xml.i -->
<node name="modbus-gateway">
  <properties>
    <help>Modbus gateway setting</help>
  </properties>
  <children>
    #include <include/serial/service/utils/ip-aliasing.xml.i>
    <leafNode name="addr-mode">
      <properties>
        <help>Choose to insert slave address or UID to message header</help>
        <completionHelp>
          <list>embedded re-mapped</list>
        </completionHelp>
        <valueHelp>
          <format>embedded</format>
          <description>The address of the slave Modbus device is embedded in the message header</description>
        </valueHelp>
        <valueHelp>
          <format>re-mapped</format>
          <description>specify the UID that will be inserted into the message header for the Modbus slave device</description>
        </valueHelp>
        <constraint>
          <regex>(embedded|re-mapped)</regex>
        </constraint>
      </properties>
      <defaultValue>embedded</defaultValue>
    </leafNode>
    <leafNode name="broadcast">
      <properties>
        <help>Enable Serial Modbus Broadcasts</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="char-timeout">
      <properties>
        <help>Specifies how long to wait, after a character to determine the end of frame (in ms)</help>
        <valueHelp>
          <format>u32:10-10000</format>
          <description>Decimal integer (10-10000)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 10-10000"/>
        </constraint>
      </properties>
      <defaultValue>30</defaultValue>
    </leafNode>
    <leafNode name="disable-exceptions">
      <properties>
        <help>Disable Modbus Exceptions</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="idle-timer">
      <properties>
        <help>Use this timer to close a connection because of inactivity (in s)</help>
        <valueHelp>
          <format>u32:0-300</format>
          <description>Decimal integer (0-300)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-300"/>
        </constraint>
      </properties>
      <defaultValue>10</defaultValue>
    </leafNode>
    <leafNode name="mess-timeout">
      <properties>
        <help>Specifies how long to wait for a response message from a Modbus TCP or serial slave before sending a Modbus exception (in ms)</help>
        <valueHelp>
          <format>u32:10-10000</format>
          <description>Decimal integer (10-10000)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 10-10000"/>
        </constraint>
      </properties>
      <defaultValue>1000</defaultValue>
    </leafNode>
    <leafNode name="next-request-delay">
      <properties>
        <help>Specifies a delay to allow serial slave to re-enable receivers before issuing next Modbus Master request (in ms)</help>
        <valueHelp>
          <format>u32:0-1000</format>
          <description>Decimal integer (0-1000)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-1000"/>
        </constraint>
      </properties>
      <defaultValue>50</defaultValue>
    </leafNode>
    <leafNode name="port">
      <properties>
        <help>Network port number that the Slave Gateway will listen on for both TCP and UDP messages </help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Port number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
      <defaultValue>502</defaultValue>
    </leafNode>
    <leafNode name="remapped-uid">
      <properties>
        <help>Specify the UID that will be inserted into the message header for the Slave Modbus serial device </help>
        <valueHelp>
          <format>u32:1-247</format>
          <description>UID number</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-247"/>
        </constraint>
      </properties>
      <defaultValue>1</defaultValue>
    </leafNode>
    <leafNode name="disable-request-queuing">
      <properties>
        <help>Disable request-queuing to not allows multiple, simultaneous messages to be queued and processed in order of reception</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="tls">
      <properties>
        <help>Enable TLS</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
