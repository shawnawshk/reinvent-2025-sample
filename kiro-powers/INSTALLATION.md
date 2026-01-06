# Installing Custom Kiro Powers

This guide explains how to install custom Kiro Powers for enhanced AI-assisted development capabilities.

## What is a Kiro Power?

A Kiro Power is a specialized configuration that gives Kiro instant expertise in specific domains or workflows. Powers use the Model Context Protocol (MCP) to provide tools, resources, and domain-specific knowledge to the AI assistant.

## Prerequisites

- **Kiro CLI** or **Kiro IDE** installed
- **AWS CLI** configured with credentials (for AWS-related powers)
- **Docker** (optional, for some MCP servers)

## Installation Methods

### Method 1: Install from Local Path (Recommended for Development)

Use this method when you have the power files locally or are developing custom powers.

#### For Kiro CLI

1. **Locate your MCP configuration file:**
   - Global scope: `~/.aws/amazonq/default.json`
   - Local scope (project-specific): `.amazonq/default.json`

2. **Add the power configuration:**

   Edit the configuration file and add an MCP server entry:

   ```json
   {
     "mcpServers": {
       "serverless-dev": {
         "type": "stdio",
         "command": "node",
         "args": ["/path/to/reinvent-2025-sample/kiro-powers/serverless-dev/mcp.json"],
         "env": {}
       }
     }
   }
   ```

3. **Restart Kiro CLI** to load the new power.

#### For Kiro IDE

1. **Open your IDE** (VS Code, JetBrains, etc.)

2. **Access the MCP configuration UI:**
   - Open the Q Developer panel
   - Open the **Chat** panel
   - Click the tools icon (⚙️)

3. **Add the MCP server:**
   - Click the plus (+) symbol
   - Select scope: **global** (available across all projects) or **local** (current project only)
   - Fill in the configuration:
     - **Name**: `serverless-dev`
     - **Transport**: `stdio`
     - **Command**: `node` (or appropriate runtime)
     - **Arguments**: `/path/to/reinvent-2025-sample/kiro-powers/serverless-dev/mcp.json`
     - **Environment variables**: (leave empty unless required)
     - **Timeout**: `30000` (30 seconds)

4. **Save** and review tool permissions

5. **Enable the MCP server** if not automatically enabled

### Method 2: Install from GitHub (For Published Powers)

Once a power is published to GitHub:

#### For Kiro CLI

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/kiro-powers.git
   cd kiro-powers
   ```

2. **Follow Method 1** using the cloned path

#### For Kiro IDE

1. **Access the MCP configuration UI** (see Method 1)

2. **Add HTTP MCP server** (if the power provides an HTTP endpoint):
   - Click the plus (+) symbol
   - Select scope: **global** or **local**
   - Fill in the configuration:
     - **Name**: `serverless-dev`
     - **Transport**: `http`
     - **URL**: `https://your-mcp-server-url.com`
     - **Headers**: (add authorization headers if required)
     - **Timeout**: `30000`

3. **Save** and authorize if prompted

## Available Powers in This Repository

### AWS Serverless Development Power

**Location:** `kiro-powers/serverless-dev/`

**Provides expertise in:**
- AWS SAM (Serverless Application Model)
- Lambda Functions
- API Gateway
- Event-Driven Architecture (EventBridge, SQS, SNS)
- DynamoDB
- Local Testing
- Security & IAM
- Performance Optimization

**Installation path:**
```
/path/to/reinvent-2025-sample/kiro-powers/serverless-dev
```

## Verifying Installation

### For Kiro CLI

1. **Check MCP server status:**
   ```bash
   kiro-cli mcp list
   ```

2. **Test the power:**
   ```bash
   kiro-cli chat
   ```
   Then ask: "What serverless capabilities do you have?"

### For Kiro IDE

1. **Open the tools panel** (⚙️ icon in Chat)

2. **Verify the MCP server is listed and enabled**

3. **Test the power** by asking domain-specific questions:
   - "Create a Lambda function with DynamoDB"
   - "Show me SAM template best practices"

## Troubleshooting

### MCP Server Not Loading

**Check configuration file syntax:**
```bash
cat ~/.aws/amazonq/default.json | jq .
```

**Verify file paths are absolute:**
- Use full paths, not relative paths
- Ensure the power directory exists

**Check permissions:**
```bash
ls -la /path/to/kiro-powers/serverless-dev/
```

### Tools Not Available

**Enable the MCP server:**
1. Open tools panel in Kiro IDE
2. Find your MCP server
3. Toggle it to enabled

**Review tool permissions:**
1. Click on the MCP server name
2. Review and approve tool permissions

### Command Not Found

**Verify the runtime is installed:**
```bash
# For Node.js-based powers
node --version

# For Python-based powers
python3 --version
```

**Install missing dependencies:**
```bash
# For Node.js
npm install

# For Python
pip install -r requirements.txt
```

## Managing Powers

### Enable/Disable a Power

**Kiro IDE:**
1. Open tools panel (⚙️)
2. Find the MCP server
3. Toggle the switch

**Kiro CLI:**
Edit `~/.aws/amazonq/default.json` and remove or comment out the server entry.

### Update a Power

1. **Pull latest changes** (if from Git):
   ```bash
   cd /path/to/kiro-powers
   git pull
   ```

2. **Restart Kiro** to reload the configuration

### Remove a Power

**Kiro IDE:**
1. Open tools panel (⚙️)
2. Find the MCP server
3. Click delete (🗑️)

**Kiro CLI:**
Remove the server entry from `~/.aws/amazonq/default.json`

## Configuration Scopes

### Global Scope
- **Location:** `~/.aws/amazonq/default.json`
- **Availability:** All projects
- **Use case:** Powers you use frequently across projects

### Local Scope
- **Location:** `.amazonq/default.json` (in project root)
- **Availability:** Current project only
- **Use case:** Project-specific powers or testing

**Note:** Local scope takes precedence over global scope.

## Security Considerations

- **Review tool permissions** before enabling any MCP server
- **Use HTTPS** for remote MCP servers
- **Validate source** of custom powers before installation
- **Limit permissions** to only what's necessary
- **Keep powers updated** to get security patches

## Additional Resources

- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
- [AWS Q Developer MCP Guide](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/mcp-ide.html)
- [Kiro CLI Documentation](https://github.com/aws/amazon-q-developer-cli)

## Support

For issues with:
- **This power:** Open an issue in this repository
- **Kiro CLI/IDE:** Refer to AWS Q Developer documentation
- **MCP protocol:** Visit the MCP community forums
