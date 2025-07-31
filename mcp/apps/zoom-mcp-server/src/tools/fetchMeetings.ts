import axios from "axios";
import { accessToken } from "../utils/zoomApi.js";
import { updateAccessToken } from "../utils/helper.js";

export async function fetchMeetings() {
  try {
    await updateAccessToken();

    const response = await axios.get("https://api.zoom.us/v2/users/me/meetings", {
      headers: {
        Authorization: `Bearer ${accessToken.token}`,
      },
    });
    return response.data;
  } catch (error: any) {
    console.error("Failed to fetch Zoom meetings:", error.response?.data || error.message);
    return null;
  }
}
