#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import { registerUserTools } from "./tools/user.js"
import { registerVideoTools } from "./tools/video.js"
import { registerSearchTools } from "./tools/search.js"

const server = new McpServer({
  name: "bilibili-mcp-server",
  version: "0.0.7",
})

async function main() {
  registerUserTools(server)
  registerVideoTools(server)
  registerSearchTools(server)
  const transport = new StdioServerTransport()
  await server.connect(transport)
  console.error("Bilibili MCP Server running on stdio")
}

main().catch((error) => {
  console.error("Fatal error in main():", error)
  process.exit(1)
})
