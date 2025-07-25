import type {
  UserInfo,
  SearchResult,
  VideoDetail,
  RelatedVideo,
} from "./types.js"
import { userAPI, videoAPI, searchAPI } from "./api.js"
import i18n from "./i18n.js"

/**
 * 获取用户信息
 */
export async function getUserInfo(mid: number): Promise<UserInfo> {
  try {
    // 获取用户基本信息
    const userInfo = (await userAPI.getInfo(mid)) || {}

    // 获取用户粉丝和关注数
    const followData = (await userAPI.getRelationStat(mid)) || {}

    // 合并数据
    userInfo.followInfo = {
      follower: followData.follower,
      following: followData.following,
    }

    return userInfo
  } catch (error) {
    console.error("Error fetching user info:", error)
    throw error
  }
}

/**
 * 搜索视频
 */
export async function searchVideos(
  keyword: string,
  page: number = 1
): Promise<SearchResult> {
  try {
    return await searchAPI.searchVideos(keyword, page) || {}
  } catch (error) {
    console.error("Error searching videos:", error)
    throw error
  }
}

/**
 * 获取视频详情
 */
export async function getVideoDetail(bvid: string): Promise<VideoDetail> {
  try {
    return await videoAPI.getDetail(bvid)
  } catch (error) {
    console.error("Error fetching video detail:", error)
    throw error
  }
}

/**
 * 获取视频相关推荐
 */
export async function getRelatedVideos(bvid: string): Promise<RelatedVideo[]> {
  try {
    return await videoAPI.getRelated(bvid)
  } catch (error) {
    console.error("Error fetching related videos:", error)
    throw error
  }
}

/**
 * 格式化时间戳
 */
export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  return date.toLocaleString()
}

/**
 * 格式化时长（秒）
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = seconds % 60

  if (hours > 0) {
    return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${remainingSeconds.toString().padStart(2, "0")}`
  } else {
    return `${minutes.toString().padStart(2, "0")}:${remainingSeconds.toString().padStart(2, "0")}`
  }
}

/**
 * 格式化用户信息
 */
export function formatUserInfo(user: UserInfo): string {
  const t = i18n.user
  const baseInfo = {
    [t.profile]: `https://space.bilibili.com/${user.mid}`,
    [t.uid]: user.mid,
  }
  const optionalInfo: Record<string, string | undefined> = {
    [t.nickname]: user.name,
    [t.followers]: user.followInfo?.follower?.toLocaleString(),
    [t.following]: user.followInfo?.following?.toLocaleString(),
    [t.level]: user.level?.toString(),
    [t.avatar]: user.face,
    [t.bio]: user.sign,
    [t.birthday]: user.birthday,
    [t.tags]: user.tags?.length > 0 ? user.tags.join(", ") : undefined,
    [t.verification]: user.official?.title,
    [t.verificationDesc]: user.official?.title
      ? user.official?.desc
      : undefined,
    [t.liveRoomUrl]: user.live_room?.url,
    [t.liveStatus]: user.live_room?.url
      ? user.live_room.liveStatus
        ? t.liveOn
        : t.liveOff
      : undefined,
  }

  let info =
    Object.entries(baseInfo)
      .map(([key, value]) => `${key}: ${value}`)
      .join("\n") + "\n"
  info += Object.entries(optionalInfo)
    .filter(([_, value]) => value !== undefined && value !== "")
    .map(([key, value]) => `${key}: ${value}`)
    .join("\n")

  return info
}
