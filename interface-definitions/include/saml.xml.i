<!-- include start from saml.xml.i -->
<node name="saml">
  <properties>
    <priority>100</priority>
    <help>Identity provider configuration</help>
  </properties>
  <children>
    <leafNode name="name">
      <properties>
        <help>Identity provider name</help>
        <valueHelp>
          <format>&lt;provider-name&gt;</format>
          <description>Name of the identity provider</description>
        </valueHelp>
      </properties>
    </leafNode>
    <leafNode name="metadata-url">
      <properties>
        <help>Identity provider metadata URL</help>
        <valueHelp>
          <format>https://idp.com/metadata</format>
          <description>Metadata URL of the identity provider</description>
        </valueHelp>
      </properties>
    </leafNode>
    <node name="user">
      <properties>
        <help>Approved users</help>
      </properties>
      <children>
        <leafNode name="admin">
          <properties>
            <help>Allowed admins for the identity provider</help>
            <multi/>
            <valueHelp>
              <format>&lt;username&gt;</format>
              <description>Username of the admin</description>
            </valueHelp>
          </properties>
        </leafNode>
        <leafNode name="operator">
          <properties>
            <help>Allowed operators for the identity provider</help>
            <multi/>
            <valueHelp>
              <format>&lt;username&gt;</format>
              <description>Username of the operator</description>
            </valueHelp>
          </properties>
        </leafNode>
      </children>
    </node>
    <node name="attribute">
      <properties>
        <help>Required and sufficient attributes for role classification</help>
      </properties>
      <children>
        <node name="operator">
          <properties>
            <help>Defines attributes for a user to be considered an operator</help>
          </properties>
          <children>
            <tagNode name="req">
              <properties>
                <help>Required attributes to be considered an operator</help>
              </properties>
              <children>
                <leafNode name="value">
                  <properties>
                    <help>Attribute required for operator</help>
                    <multi/>
                    <valueHelp>
                      <format>&lt;value&gt;</format>
                      <description>Required value(s)</description>
                    </valueHelp>
                  </properties>
                </leafNode>
              </children>
            </tagNode>
            <tagNode name="suff">
              <properties>
                <help>Sufficient attributes to be considered an operator</help>
              </properties>
              <children>
                <leafNode name="value">
                  <properties>
                    <help>Attribute sufficient for operator</help>
                    <multi/>
                    <valueHelp>
                      <format>&lt;value&gt;</format>
                      <description>Sufficient value(s)</description>
                    </valueHelp>
                  </properties>
                </leafNode>
              </children>
            </tagNode>
          </children>
        </node>
        <node name="admin">
          <properties>
            <help>Defines attributes for a user to be considered an admin</help>
          </properties>
          <children>
            <tagNode name="req">
              <properties>
                <help>Required attributes to be considered an admin</help>
              </properties>
              <children>
                <leafNode name="value">
                  <properties>
                    <help>Attribute required for admin</help>
                    <multi/>
                    <valueHelp>
                      <format>&lt;value&gt;</format>
                      <description>Allowed value(s)</description>
                    </valueHelp>
                  </properties>
                </leafNode>
              </children>
            </tagNode>
            <tagNode name="suff">
              <properties>
                <help>Sufficient attributes to be considered an admin</help>
              </properties>
              <children>
                <leafNode name="value">
                  <properties>
                    <help>Attribute sufficient for admin</help>
                    <multi/>
                    <valueHelp>
                      <format>&lt;value&gt;</format>
                      <description>Sufficient value(s)</description>
                    </valueHelp>
                  </properties>
                </leafNode>
              </children>
            </tagNode>
          </children>
        </node>
      </children>
    </node>
    <leafNode name="default-sso-level">
      <properties>
        <help>Default level for SSO users</help>
        <valueHelp>
          <format>operator || admin</format>
          <description>Default privilege level for SSO users</description>
        </valueHelp>
        <constraint>
          <regex>^(operator|admin)$</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->
