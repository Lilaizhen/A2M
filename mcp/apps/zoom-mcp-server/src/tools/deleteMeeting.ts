import axios from "axios";
import { accessToken } from "../utils/zoomApi.js";
import { updateAccessToken } from "../utils/helper.js";

export async function deleteZoomMeeting({ id }: { id: string }) {
  const endpoint = `https://api.zoom.us/v2/meetings/${id}`;

  try {

    await updateAccessToken();

    await axios.delete(endpoint, {
      headers: {
        Authorization: `Bearer ${accessToken.token}`,
        "Content-Type": "application/json",
      },
    });

    return { success: true, message: `Meeting ${id} deleted.` };
  } catch (error: any) {
    console.error("Failed to delete Zoom meeting:", error.response?.data || error.message);
    throw new Error("Unable to delete meeting");
  }
}
