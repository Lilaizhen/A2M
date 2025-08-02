import fetch from "node-fetch"
import type {
  BiliResponse,
  UserInfo,
  VideoDetail,
  RelatedVideo,
  SearchResult,
} from "./types.js"
import { wbiSignParamsQuery } from "./wbi.js"

if (!globalThis.fetch) {
  globalThis.fetch = fetch as unknown as typeof global.fetch
}

const BASE_URL = "https://api.bilibili.com"

// 默认请求头
const DEFAULT_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
  Referer: "https://www.bilibili.com",
  Cookie: "buvid3=randomstring; path=/; domain=.bilibili.com",
}

/**
 * 发起 API 请求的通用函数
 * @param endpoint API 端点
 * @param params 请求参数
 */
export async function apiRequest<T>(
  endpoint: string,
  params?: Record<string, string | number>
): Promise<T> {
  let url = `${BASE_URL}${endpoint}`

  if (params) {
    //  使用 WBI 签名
    const signedParams = await wbiSignParamsQuery(params)
    url += `?${signedParams}`
  }

  const response = await fetch(url, {
    headers: DEFAULT_HEADERS,
  })

  if (!response.ok) {
    throw new Error(
      `API request failed: ${response.status} ${response.statusText}`
    )
  }

  const data = (await response.json()) as BiliResponse<T>

  if (data.code !== 0) {
    throw new Error(`API returned error: ${data.message || "Unknown error"}`)
  }

  return data.data
}

/**
 * 用户相关 API
 */
export const userAPI = {
  /**
   * 获取用户信息
   */
  async getInfo(mid: number) {
    return await apiRequest<UserInfo>("/x/space/wbi/acc/info", { mid })
  },

  /**
   * 获取用户关注和粉丝数
   */
  async getRelationStat(mid: number) {
    return await apiRequest<{ follower: number; following: number }>(
      "/x/relation/stat",
      { vmid: mid }
    )
  },
}

/**
 * 视频相关 API
 */
export const videoAPI = {
  /**
   * 获取视频详情
   */
  async getDetail(bvid: string) {
    return await apiRequest<VideoDetail>("/x/web-interface/view", { bvid })
  },

  /**
   * 获取视频相关推荐
   */
  async getRelated(bvid: string) {
    return await apiRequest<RelatedVideo[]>(
      "/x/web-interface/related/recommend",
      { bvid }
    )
  },
}

/**
 * 搜索相关 API
 */
export const searchAPI = {
  /**
   * 搜索视频
   */
  async searchVideos(keyword: string, page: number = 1) {
    return await apiRequest<SearchResult>("/x/web-interface/search/all/v2", {
      keyword,
      page,
      search_type: "video",
    })
  },
}
