/**
 * 用户信息
 */
export interface UserInfo {
  mid: number
  /** 用户名 */
  name: string
  /** 头像图片地址 */
  face: string
  /** 个性签名 */
  sign: string
  /** 等级 */
  level: number
  /** 生日 */
  birthday: string
  /** 标签 */
  tags: string[]
  live_room: {
    /** 直播间状态 0: 未开播 1: 开播 */
    liveStatus: 0 | 1
    /** 直播间地址 */
    url: string
    watched_show: {
      /** 多少人看过 */
      text_small: number
    }
  }
  official: {
    role: number
    title: string
    desc: string
  } | null
  vip: {
    type: number
    status: number
  }
  followInfo: {
    /** 粉丝数 */
    follower: number
    /** 关注数 */
    following: number
  }
  /** 调用失败 */
  v_voucher: any
}
export interface BiliResponse<T> {
  code: number
  message: string
  ttl?: number
  data: T
}

export interface SearchResult {
  seid: string
  page: number
  pagesize: number
  numResults: number
  numPages: number
  result: Array<{
    result_type: string
    data: (VideoSearchItem | UserSearchItem)[]
  }>
}

/**
 * 视频详情
 */
export interface VideoDetail {
  bvid: string
  aid: number
  title: string
  desc: string
  pic: string
  owner: {
    mid: number
    name: string
    face: string
  }
  stat: {
    view: number
    danmaku: number
    reply: number
    favorite: number
    coin: number
    share: number
    like: number
  }
  duration: number
  cid: number
  pubdate: number
  ctime: number
  tags: string[]
}

/**
 * 相关视频推荐
 */
export interface RelatedVideo {
  bvid: string
  aid: number
  title: string
  pic: string
  owner: {
    mid: number
    name: string
  }
  stat: {
    view: number
    danmaku: number
  }
  duration: number
}

export interface VideoSearchItem {
  type: "video"
  id: number
  bvid: string
  /** 地址 */
  arcurl: string
  /** 标题 */
  title: string
  /** 简介 */
  description: string
  /** 作者 */
  author: string
  /** 播放数 */
  play: number
  /** 弹幕数 */
  danmaku: number
  /** 点赞数 */
  like: number
  /** 类型 */
  typename: string
  /** 时长 */
  duration: string
  /** 发布时间 (单位/秒) */
  pubdate: number
}

export interface UserSearchItem {
  type: "user"
  mid: number
  name: string
  face: string
  fans: number
  level: number
  official: {
    role: number
    title: string
  } | null
  sign: string
  videos?: number
}
