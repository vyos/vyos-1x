<!-- include start from serial/service/ppp.xml.i -->
<node name="ppp">
  <properties>
    <help>PPP profile</help>
  </properties>
  <children>
    <node name = "authentication">
      <properties>
        <help>authentication setting</help>
      </properties>
      <children>
        <leafNode name="protocol">
          <properties>
            <help>authentication protocol</help>
            <completionHelp>
              <list>chap pap none</list>
            </completionHelp>
            <constraint>
              <regex>(chap|pap|none)</regex>
            </constraint>
          </properties>
          <defaultValue>chap</defaultValue>
        </leafNode>
        <leafNode name="chap-challenge-interval">
          <properties>
            <help>The interval to issue a CHAP re-challenge to the remote end</help>
            <valueHelp>
              <format>u32:0-255</format>
              <description>(in minutes)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-255"/>
            </constraint>
          </properties>
          <defaultValue>0</defaultValue>
        </leafNode>
        <leafNode name="username">
          <properties>
            <help>CHAP or PAP username</help>
            <constraint>
              <regex>.{0,255}</regex>
            </constraint>
            <constraintErrorMessage>PPP username too long (limit 255 characters)</constraintErrorMessage>
          </properties>
        </leafNode>
        <leafNode name="password">
          <properties>
            <help>CHAP or PAP password</help>
            <constraint>
              <regex>.{0,17}</regex>
            </constraint>
            <constraintErrorMessage>PPP password too long (limit 17 characters)</constraintErrorMessage>
          </properties>
        </leafNode>
        <leafNode name="remote-user">
          <properties>
            <help>CHAP or PAP remote username</help>
            <constraint>
              <regex>.{0,255}</regex>
            </constraint>
            <constraintErrorMessage>PPP remote username too long (limit 255 characters)</constraintErrorMessage>
          </properties>
        </leafNode>
        <leafNode name="remote-password">
          <properties>
            <help>CHAP or PAP remote password</help>
            <constraint>
              <regex>.{0,17}</regex>
            </constraint>
            <constraintErrorMessage>PPP remote password too long (limit 17 characters)</constraintErrorMessage>
          </properties>
        </leafNode>
        <leafNode name="timeout">
          <properties>
            <help>The timeout during which successful authentication must take place</help>
            <valueHelp>
              <format>u32:0-255</format>
              <description>(in minutes)</description>
            </valueHelp>
            <constraint>
              <validator name="numeric" argument="--range 0-255"/>
            </constraint>
          </properties>
          <defaultValue>1</defaultValue>
        </leafNode>
      </children>
    </node>
    <leafNode name="local-address">
      <properties>
        <help>The IPV4 IP address of the IGOS end of the PPP link</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-host"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="remote-address">
      <properties>
        <help>The IPV4 IP address of the remote end of the PPP link</help>
        <valueHelp>
          <format>ipv4</format>
          <description>IPv4 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-host"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="accm">
      <properties>
        <help>Specifies the ACCM (Asynchronous Control Character Map) characters that should be escaped from the data stream</help>
        <constraint>
          <regex>.{8,8}</regex>
        </constraint>
        <constraintErrorMessage>hex value must be 8 digits long</constraintErrorMessage>
      </properties>
      <defaultValue>00000000</defaultValue>
    </leafNode>
    <leafNode name="disable-ac-comp">
      <properties>
        <help>Disable compression of the PPP Address and Control fields</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="configure-request-retry">
      <properties>
        <help>Maximum number of LCP configure-requesttransmissions</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>Times</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
      <defaultValue>2</defaultValue>
    </leafNode>
    <leafNode name="configure-request-timeout">
      <properties>
        <help>The LCP restart interval (retransmission timeout)</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>(in seconds)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>3</defaultValue>
    </leafNode>
    <leafNode name="echo-retry">
      <properties>
        <help>The maximum number of times an echo request packet will be re-sent before the link is terminated</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>Times</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
      <defaultValue>3</defaultValue>
    </leafNode>
    <leafNode name="echo-timeout">
      <properties>
        <help>The maximum time, in seconds, between sending an echo request packet if no response is received from the remote host</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>(in seconds)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
      <defaultValue>30</defaultValue>
    </leafNode>
    <leafNode name="ip-address-negotiation">
      <properties>
        <help>Enable ip address negotiation to allow the remote end to specify its IP address</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="ipv6-global-network-prefix">
      <properties>
        <help>Specify an IPv6 global network prefix that the IGOS will advertise to the device at the other end of the PPP link</help>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-host"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="ipv6-local-interface">
      <properties>
        <help>The local IPv6 interface identifier of the IGOS end of the PPP link (format and val need to be checked)</help>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-address"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="ipv6-remote-interface">
      <properties>
        <help>The remote IPv6 interface identifier of the remote end of the PPP link (format and val need to be checked)</help>
        <valueHelp>
          <format>ipv6</format>
          <description>IPv6 address</description>
        </valueHelp>
        <constraint>
          <validator name="ipv6-address"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="magic-negotiation">
      <properties>
        <help>Enable random numbers sent on the link if a line is looping back</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="mru">
      <properties>
        <help>The Maximum Receive Unit (MRU) parameter specifies the maximum size of PPP packets that the IOLAN’s port will accept</help>
        <valueHelp>
          <format>u32:64-1500</format>
          <description>(in bytes)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 64-1500"/>
        </constraint>
      </properties>
      <defaultValue>1500</defaultValue>
    </leafNode>
    <leafNode name="nak-retry">
      <properties>
        <help>The maximum number of times a configure NAK packet will be re-sent before the link is terminated</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>Times</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
      <defaultValue>10</defaultValue>
    </leafNode>
    <leafNode name="disable-protocol-comp">
      <properties>
        <help>Disable compression of the PPP Protocol field</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="routing">
      <properties>
        <help>Determines the routing mode (RIP, Routing Information Protocol) used on the PPP interface</help>
        <completionHelp>
          <list>listen send none both</list>
        </completionHelp>
        <constraint>
          <regex>(listen|send|none)</regex>
        </constraint>
      </properties>
      <defaultValue>none</defaultValue>
    </leafNode>
    <leafNode name="terminate-request-retry">
      <properties>
        <help>The maximum number of times a terminate request packet will be re-sent before the link is terminated</help>
        <valueHelp>
          <format>u32:0-255</format>
          <description>(in seconds)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-255"/>
        </constraint>
      </properties>
      <defaultValue>2</defaultValue>
    </leafNode>
    <leafNode name="terminate-request-timeout">
      <properties>
        <help>The maximum time that LCP (Link Control Protocol) will wait before it considers a terminate request packet to have been lost</help>
        <valueHelp>
          <format>u32:1-255</format>
          <description>(in seconds)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-255"/>
        </constraint>
      </properties>
      <defaultValue>3</defaultValue>
    </leafNode>
    <leafNode name="disable-vj-comp">
      <properties>
        <help>Disable Van Jacobson style TCP/IP header compression in both the transmit and the receive direction</help>
        <valueless/>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
