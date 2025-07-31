import { Meet, NewMeeting } from "./types.js";

export function formatMeet(meeting: Meet): string {
  return [
    `Id: ${meeting.id || "Unknown"}`,
    `Topic: ${meeting.topic || "Unknown"}`,
    `Start Time: ${meeting.start_time || "Unknown"}`,
    `Duration: ${meeting.duration || "Unknown"}`,
    `Time Zone: ${meeting.timezone || "Unknown"}`,
    `Join URL: ${meeting.join_url || "Unknown"}`,
    `Password: ${meeting.password || "Unknown"}`,
    "---",
  ].join("\n");
}

export function formatCreateMeet(meeting: NewMeeting): string {
  return [
    `Topic: ${meeting.topic || "Unknown"}`,
    `Start Time: ${meeting.start_time || "Unknown"}`,
    `Duration: ${meeting.duration || "Unknown"}`,
    `Time Zone: ${meeting.timezone || "Unknown"}`,
    `Agenda: ${meeting.agenda || "Unknown"}`,
    `Join URL: ${meeting.join_url || "Unknown"}`,
    `Password: ${meeting.password || "Unknown"}`,
  ].join("\n");
}
