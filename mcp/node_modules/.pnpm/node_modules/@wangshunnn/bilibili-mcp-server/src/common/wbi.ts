/**
 * Reference: JavaScript implementation from Bilibili-API-Collect
 * https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/misc/sign/wbi.md#javascript
 * Thanks!
 */

import crypto from "node:crypto"

/**
 * WBI密钥接口
 */
interface WbiKeys {
  img_key: string
  sub_key: string
}

/**
 * 混合密钥编码表 - 用于WBI签名算法
 */
const mixinKeyEncTab: number[] = [
  46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
  33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61,
  26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36,
  20, 34, 44, 52,
]

/**
 * 对 imgKey 和 subKey 进行字符顺序打乱编码
 * @param orig 原始密钥字符串
 * @returns 混合后的密钥
 */
const getMixinKey = (orig: string): string =>
  mixinKeyEncTab
    .map((n) => orig[n])
    .join("")
    .slice(0, 32)

/**
 * 为请求参数进行 wbi 签名
 * @param params 请求参数对象
 * @param img_key 图片密钥
 * @param sub_key 子密钥
 * @returns 签名后的查询字符串
 */
function encWbi(
  params: Record<string, string | number>,
  img_key: string,
  sub_key: string
): string {
  const mixin_key: string = getMixinKey(img_key + sub_key),
    curr_time: number = Math.round(Date.now() / 1000),
    chr_filter: RegExp = /[!'()*]/g

  // 创建一个新对象，避免修改原始对象
  const signParams: Record<string, string | number> = {
    ...params,
    wts: curr_time,
  }

  // 按照 key 重排参数
  const query: string = Object.keys(signParams)
    .sort()
    .map((key) => {
      // 过滤 value 中的 "!'()*" 字符
      const value: string = signParams[key].toString().replace(chr_filter, "")
      return `${encodeURIComponent(key)}=${encodeURIComponent(value)}`
    })
    .join("&")

  const wbi_sign: string = crypto
    .createHash("md5")
    .update(query + mixin_key)
    .digest("hex") // 计算 w_rid

  return query + "&w_rid=" + wbi_sign
}

/**
 * 获取最新的 img_key 和 sub_key
 * @returns WBI密钥对象
 */
async function getWbiKeys(): Promise<WbiKeys> {
  interface NavResponse {
    data: {
      wbi_img: {
        img_url: string
        sub_url: string
      }
    }
  }

  const res = await fetch("https://api.bilibili.com/x/web-interface/nav", {
    headers: {
      // SESSDATA 字段
      Cookie: "SESSDATA=xxxxxx",
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
      Referer: "https://www.bilibili.com/",
    },
  })

  const data: NavResponse = await res.json()

  const img_url: string = data.data.wbi_img.img_url
  const sub_url: string = data.data.wbi_img.sub_url

  return {
    img_key: img_url.slice(
      img_url.lastIndexOf("/") + 1,
      img_url.lastIndexOf(".")
    ),
    sub_key: sub_url.slice(
      sub_url.lastIndexOf("/") + 1,
      sub_url.lastIndexOf(".")
    ),
  }
}

/**
 * 使用WBI签名生成查询字符串
 * @param params 要签名的参数对象
 * @returns 签名后的查询字符串
 */
export async function wbiSignParamsQuery(
  params: Record<string, string | number>
): Promise<string> {
  const web_keys: WbiKeys = await getWbiKeys()
  return encWbi(params, web_keys.img_key, web_keys.sub_key)
}

/**
 * 为了方便使用的WBI签名功能导出对象
 */
export const wbiSign = {
  /**
   * 使用WBI签名生成完整的参数对象
   * @param params 要签名的参数对象
   * @returns 签名后的参数对象，包含w_rid和wts
   */
  async sign(
    params: Record<string, string | number>
  ): Promise<Record<string, string | number>> {
    const queryString: string = await wbiSignParamsQuery(params)
    const urlParams = new URLSearchParams(queryString)
    const signedParams: Record<string, string> = {}

    urlParams.forEach((value, key) => {
      signedParams[key] = value
    })

    return signedParams
  },
}
