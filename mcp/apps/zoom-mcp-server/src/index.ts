#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { fetchMeetings } from "./tools/fetchMeetings.js";
import { formatCreateMeet, formatMeet } from "./utils/format.js";
import { createZoomMeeting } from "./tools/createMeeting.js";
import { NewMeeting } from "./utils/types.js";
import { updateZoomMeeting } from "./tools/updateMeeting.js";
import { deleteZoomMeeting } from "./tools/deleteMeeting.js";

const server = new McpServer({
  name: "zoom-mcp",
  version: "1.0.0",
});

server.tool(
  "get_meetings",
  "Retrieve all active Zoom meetings",
  {},
  async () => {
    const data = await fetchMeetings();

    if (!data) {
      return {
        content: [{ type: "text", text: "Error fetching meetings" }],
      };
    }

    const meetings = data.meetings || [];
    if (meetings.length === 0) {
      return {
        content: [{ type: "text", text: "No active meetings" }],
      };
    }

    const formatted = meetings.map(formatMeet).join("\n");
    return {
      content: [{ type: "text", text: `Active meetings:\n\n${formatted}` }],
    };
  }
);

server.tool(
  "create_meeting",
  "Create a new Zoom meeting",
  {
    topic: z.string().describe("Meeting topic"),
    start_time: z.string().describe("Start time"),
    timezone: z.string().describe("Timezone"),
    duration: z.number().min(0).describe("Duration in minutes"),
    agenda: z.string().describe("Meeting agenda"),
  },
  async (params) => {
    const data = await createZoomMeeting(params);

    if (!data) {
      return {
        content: [{ type: "text", text: "Error creating meeting" }],
      };
    }

    const meeting: NewMeeting = {
      topic: data.topic,
      start_time: data.start_time,
      duration: data.duration,
      timezone: data.timezone,
      join_url: data.join_url,
      password: data.password,
      agenda: data.agenda || "",
    };

    const formatted = formatCreateMeet(meeting);
    return {
      content: [{ type: "text", text: `Meeting created:\n\n${formatted}` }],
    };
  }
);

server.tool(
  "update_meeting",
  "Update an existing Zoom meeting",
  {
    id: z.string().describe("Meeting ID"),
    topic: z.string().describe("Updated topic"),
    start_time: z.string().describe("Updated start time"),
    duration: z.number().describe("Updated duration"),
    timezone: z.string().describe("Updated timezone"),
    agenda: z.string().describe("Updated agenda"),
  },
  async (params) => {
    const data = await updateZoomMeeting(params);

    if (!data?.success) {
      return {
        content: [{ type: "text", text: "Error updating the meeting" }],
      };
    }

    return {
      content: [{ type: "text", text: `Update successful: ${data.success}` }],
    };
  }
);

server.tool(
  "delete_meeting",
  "Delete an existing Zoom meeting",
  {
    id: z.string().describe("Meeting ID"),
  },
  async (params) => {
    const data = await deleteZoomMeeting(params);

    if (!data?.success) {
      return {
        content: [{ type: "text", text: "Error deleting the meeting" }],
      };
    }

    return {
      content: [{ type: "text", text: `Deletion successful: ${data.success}` }],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Zoom MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});
