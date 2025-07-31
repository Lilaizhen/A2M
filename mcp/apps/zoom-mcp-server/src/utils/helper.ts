import { accessToken, fetchZoomAccessToken } from "./zoomApi.js";

function isLessThanOneHour(inputTime: string): boolean {
    const inputDate = new Date(inputTime);
    const currentDate = new Date();

    const timeDifference = currentDate.getTime() - inputDate.getTime();

    const oneHourInMillis = 1000 * 60 * 60;

    return timeDifference < oneHourInMillis;
}

export async function updateAccessToken() {
    try {
        if(accessToken.token === '' || accessToken.lastUpdated === '' || !isLessThanOneHour(accessToken.lastUpdated)) {
            accessToken.token = await fetchZoomAccessToken();
            const currentDate = new Date;
            accessToken.lastUpdated = currentDate.toString();
        }
        return {
            success: true
        }
    } catch (error: any) {
        console.log(error.message);
        throw new Error('Error updating the access token.');
    }
}