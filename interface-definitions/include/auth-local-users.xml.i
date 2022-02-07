<!-- include start from auth-local-users.xml.i -->
<node name="local-users">
  <properties>
    <help>Local user authentication</help>
  </properties>
  <children>
    <tagNode name="username">
      <properties>
        <help>Username used for authentication</help>
        <valueHelp>
          <format>txt</format>
          <description>Username used for authentication</description>
        </valueHelp>
      </properties>
      <children>
        #include <include/generic-disable-node.xml.i>
        <leafNode name="password">
          <properties>
            <help>Password used for authentication</help>
          </properties>
        </leafNode>
        <node name="otp">
          <properties>
            <help>2FA OTP authentication parameters</help>
          </properties>
          <children>
            <leafNode name="key">
              <properties>
                <help>Token Key Secret key for the token algorithm (see RFC 4226)</help>
                <valueHelp>
                  <format>txt</format>
                  <description>OTP key in hex-encoded format</description>
                </valueHelp>
                <constraint>
                  <regex>[a-fA-F0-9]{20,10000}</regex>
                </constraint>
                <constraintErrorMessage>Key name must in hex be alphanumerical only (min. 20 hex characters)</constraintErrorMessage>
              </properties>
            </leafNode>
            <leafNode name="otp-length">
              <properties>
                <help>Optional. Number of digits in OTP code (default: 6)</help>
                <valueHelp>
                  <format>u32:6-8</format>
                  <description>Number of digits in OTP code (default: 6)</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 6-8"/>
                </constraint>
                <constraintErrorMessage>Number of digits in OTP code must be between 6 and 8</constraintErrorMessage>
              </properties>
            </leafNode>
            <leafNode name="interval">
              <properties>
                <help>Optional. Time tokens interval in seconds (for time tokens) (default: 30)</help>
                <valueHelp>
                  <format>u32:5-86400</format>
                  <description>Time tokens interval in seconds (for time tokens). (default: 30)</description>
                </valueHelp>
                <constraint>
                  <validator name="numeric" argument="--range 5-86400"/>
                </constraint>
                <constraintErrorMessage>Time token interval must be between 5 and 86400 seconds</constraintErrorMessage>
              </properties>
            </leafNode>
            <leafNode name="token-type">
              <properties>
                <help>Optional. Token type (default: hotp-time)</help>
                <valueHelp>
                  <format>hotp-time</format>
                  <description>time-based OTP algorithm</description>
                </valueHelp>
                <valueHelp>
                  <format>hotp-event</format>
                  <description>event-based OTP algorithm</description>
                </valueHelp>
                <constraint>
                  <regex>(hotp-time|hotp-event)</regex>
                </constraint>
                <completionHelp>
                  <list>hotp-time hotp-event</list>
                </completionHelp>
              </properties>
            </leafNode>
          </children>
        </node>
      </children>
    </tagNode>
  </children>
</node>
<!-- include end -->
