import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { formatUserInfo, getUserInfo } from "../common/utils.js"

export function registerUserTools(server: McpServer): void {
  server.tool(
    "get_user_info",
    "Get information about a Bilibili user",
    {
      mid: z.number().int().positive().describe("User's numeric ID"),
    },
    async ({ mid }) => {
      try {
        const userInfo = await getUserInfo(mid) || {}
        const formattedInfo = formatUserInfo(userInfo)

        return {
          content: [
            {
              type: "text",
              text: formattedInfo,
            },
          ],
        }
      } catch (error) {
        return {
          content: [
            {
              type: "text",
              text: `get user info failed: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        }
      }
    }
  )
}
