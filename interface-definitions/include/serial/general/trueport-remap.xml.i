<!-- include start from serial/general/trueport-remap.xml.i -->
<node name="trueport-remap">
  <properties>
    <help>Trueport baud rate remapping setting</help>
  </properties>
  <children>
    <node name="speed">
      <properties>
        <help>Trueport baud rate (running on the application software)</help>
      </properties>
      <children>
        <node name="50">
          <properties>
            <help>50 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>57600</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="75">
          <properties>
            <help>75 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>300</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="110">
          <properties>
            <help>110 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>115200</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="134">
          <properties>
            <help>134 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>230400</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="150">
          <properties>
            <help>150 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>300</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="200">
          <properties>
            <help>200 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>300</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="300">
          <properties>
            <help>300 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>300</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="600">
          <properties>
            <help>600 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>600</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="1200">
          <properties>
            <help>1200 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>1200</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="1800">
          <properties>
            <help>1800 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>1800</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="2400">
          <properties>
            <help>2400 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>2400</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="4800">
          <properties>
            <help>4800 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>4800</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="9600">
          <properties>
            <help>9600 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>9600</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="19200">
          <properties>
            <help>19200 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>19200</defaultValue>
            </leafNode>
          </children>
        </node>
        <node name="38400">
          <properties>
            <help>38400 remap to</help>
          </properties>
          <children>
            #include <include/serial/general/remap-util.xml.i>
            <leafNode name="remap">
              <defaultValue>38400</defaultValue>
            </leafNode>
          </children>
        </node>
      </children>
    </node>
  </children>
</node>
<!-- include end -->
