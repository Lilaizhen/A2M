#!/usr/bin/env node

const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");
const axios = require("axios");

/**
 * 一个简单的异步任务并发控制器。
 * 用于替代外部依赖 `p-limit`，以保证代码的兼容性和独立性。
 * @param {number} concurrency - 最大并发执行数量。
 * @returns {function(function): Promise<any>} - 一个接收异步函数并进行调度的函数。
 */
function simplePool(concurrency) {
    const queue = [];
    let activeCount = 0;

    const runTask = (task) => {
        activeCount++;
        task.fn()
            .then(res => task.resolve(res))
            .catch(err => task.reject(err))
            .finally(() => {
                activeCount--;
                processQueue();
            });
    };

    const processQueue = () => {
        if (activeCount < concurrency && queue.length > 0) {
            const task = queue.shift();
            runTask(task);
        }
    };

    return (fn) => {
        return new Promise((resolve, reject) => {
            queue.push({ fn, resolve, reject });
            processQueue();
        });
    };
}


/**
 * @class BilibiliAPI
 * @description 封装所有与 Bilibili API 的网络交互逻辑。
 */
class BilibiliAPI {
  constructor() {
    // 初始化 axios 实例，用于发送网络请求
    this.axiosInstance = axios.create({
      timeout: 15000, // 设置全局请求超时
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Origin": "https://www.bilibili.com"
      }
    });
    // 统一定义 Bilibili API 的各个端点
    this.apiEndpoints = {
      view: "https://api.bilibili.com/x/web-interface/view",
      reply: "https://api.bilibili.com/x/v2/reply",
      replyReply: "https://api.bilibili.com/x/v2/reply/reply",
    };
  }

  /**
   * 根据 bvid 获取视频的基本信息（主要是 aid 和标题）。
   * @param {string} bvid - 视频的 BV 号。
   * @param {string} cookie - 用户的 Bilibili Cookie。
   * @returns {Promise<{aid: number, title: string}>} - 包含 aid 和 title 的对象。
   */
  async getVideoInfo(bvid, cookie) {
    try {
      const response = await this.axiosInstance.get(this.apiEndpoints.view, {
        params: { bvid },
        headers: {
          "Cookie": cookie,
          "Referer": `https://www.bilibili.com/video/${bvid}`,
        },
      });

      if (response.data.code !== 0) {
        throw new Error(`获取视频信息失败 (${response.data.code}): ${response.data.message}`);
      }
      
      return { aid: response.data.data.aid, title: response.data.data.title };
    } catch (error) {
      throw new Error(`获取视频信息失败: ${error.message || "未知网络错误"}`);
    }
  }

  /**
   * 获取视频的主评论列表。
   * @param {number} oid - 视频的 aid。
   * @param {number} page - 评论页码。
   * @param {number} pageSize - 每页评论数量。
   * @param {number} sort - 排序方式 (0: 时间, 1: 热度)。
   * @param {string} cookie - 用户的 Bilibili Cookie。
   * @param {string} videoId - 用于 Referer 的视频 ID (bvid 或 av号)。
   * @returns {Promise<import('axios').AxiosResponse<any, any>>} - axios 的原始响应对象。
   */
  async fetchComments(oid, page, pageSize, sort, cookie, videoId) {
    try {
      const response = await this.axiosInstance.get(this.apiEndpoints.reply, {
        params: { type: 1, oid, pn: page, ps: Math.min(pageSize, 49), sort },
        headers: {
          "Cookie": cookie,
          "Referer": `https://www.bilibili.com/video/${videoId}`,
        },
      });
      return response;
    } catch (error) {
      if (error.code === 'ECONNABORTED') throw new Error("请求超时，请稍后重试");
      throw new Error(`获取主评论失败: ${error.message || "未知网络错误"}`);
    }
  }

  /**
   * 获取单条主评论下的楼中楼回复。
   * @param {number} oid - 视频的 aid。
   * @param {number} parentRpid - 父评论的 rpid。
   * @param {string} cookie - 用户的 Bilibili Cookie。
   * @param {string} videoId - 用于 Referer 的视频 ID (bvid 或 av号)。
   * @returns {Promise<Array<any>|'fetch_failed'>} - 回复数组；若失败则返回特定错误标识。
   */
  async fetchReplies(oid, parentRpid, cookie, videoId) {
    try {
      const response = await this.axiosInstance.get(this.apiEndpoints.replyReply, {
        params: { type: 1, oid, root: parentRpid, ps: 10 }, // 固定获取前10条回复
        headers: {
          "Cookie": cookie,
          "Referer": `https://www.bilibili.com/video/${videoId}`,
        },
        timeout: 8000,
      });

      if (response.data.code === 0 && response.data.data?.replies) {
        return response.data.data.replies;
      }
      return []; // API 成功但没有回复，返回空数组
    } catch (error) {
      // 捕获任何错误（网络、超时等），返回一个特定标识以便上层处理
      console.error(`获取楼中楼失败 (rpid: ${parentRpid}):`, error.message);
      return 'fetch_failed';
    }
  }
}

/**
 * @class BilibiliMCPServer
 * @description MCP 服务器的主体实现，负责定义工具和处理请求。
 */
class BilibiliMCPServer {
  constructor() {
    // 初始化 MCP 服务器，添加必需的版本信息
    this.server = new Server(
      { 
        name: "bilibili-comments-tool",
        version: "1.0.0"
      },
      { capabilities: { tools: {} } }
    );
    this.bilibiliAPI = new BilibiliAPI();
    this.setupToolHandlers();
  }

  /**
   * 设置工具的定义和请求处理逻辑。
   */
  setupToolHandlers() {
    // 处理 `listTools` 请求，向客户端声明本工具的存在和能力
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [{
          name: "get_video_comments",
          description: "获取 B 站视频的评论内容，支持分页、排序和楼中楼回复。注意：需要有效的 B 站 Cookie 才能正常工作。",
          inputSchema: {
            type: "object",
            properties: {
              bvid: { type: "string", description: "B 站视频 BV 号（与 aid 二选一）" },
              aid: { type: "string", description: "B 站视频 AV 号（与 bvid 二选一）" },
              page: { type: "number", default: 1, description: "页码，默认为 1" },
              pageSize: { type: "number", default: 20, description: "每页数量，范围 1-49，默认 20" },
              sort: { type: "number", default: 0, description: "排序方式: 0 按时间，1 按热度" },
              includeReplies: { type: "boolean", default: true, description: "是否包含楼中楼回复" },
              cookie: { type: "string", description: "B 站 Cookie（可选）。如果已设置环境变量，则无需提供。" }
            },
          }
        }]
      };
    });

    // 处理 `callTool` 请求，当 LLM 决定调用本工具时执行
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      if (request.params.name === "get_video_comments") {
        return await this.getVideoComments(request.params.arguments);
      }
      throw new Error(`未知的工具: ${request.params.name}`);
    });
  }
  
  /**
   * 简单校验 Cookie 字符串是否有效。
   * @param {string} cookie - 待校验的 Cookie。
   * @returns {boolean}
   */
  validateCookie(cookie) {
    return cookie && typeof cookie === 'string' && cookie.includes('SESSDATA');
  }

  /**
   * `get_video_comments` 工具的核心执行函数。
   * @param {object} args - 从 LLM 客户端传来的参数。
   * @returns {Promise<{content: [{type: string, text: string}]}>} - MCP 格式的返回结果。
   */
  async getVideoComments(args) {
    try {
      // 1. 参数校验与准备
      const { bvid, aid, page = 1, pageSize = 20, sort = 0, includeReplies = true } = args;
      const cookie = args.cookie || process.env.BILIBILI_COOKIE;

      if (!this.validateCookie(cookie)) {
        throw new Error("必须提供有效的 B 站 Cookie。请通过参数传入或设置 BILIBILI_COOKIE 环境变量。");
      }
      if (!bvid && !aid) throw new Error("必须提供 bvid 或 aid 之一");
      if (pageSize < 1 || pageSize > 49) throw new Error("pageSize 必须在 1-49 之间");
      if (![0, 1].includes(sort)) throw new Error("sort 必须是 0 或 1");

      // 2. 获取评论数据
      const videoIdForRef = bvid || `av${aid}`;
      let oid = aid;
      if (bvid && !aid) {
        // 如果只提供了 bvid，需要先转换为 aid
        const videoInfo = await this.bilibiliAPI.getVideoInfo(bvid, cookie);
        oid = videoInfo.aid;
      }

      const response = await this.bilibiliAPI.fetchComments(oid, page, pageSize, sort, cookie, videoIdForRef);
      
      if (response.data.code !== 0) {
        let errorMsg = response.data.message;
        if (response.data.code === -101) errorMsg = "账号未登录或 Cookie 已过期";
        else if (response.data.code === -403) errorMsg = "访问权限不足";
        else if (response.data.code === -404) errorMsg = "视频不存在或已被删除";
        throw new Error(`B 站 API 错误 (${response.data.code}): ${errorMsg}`);
      }

      // 3. 将数据格式化为 Markdown 报告
      const markdownResponse = await this.generateMarkdownResponse(
        response.data.data, 
        includeReplies, 
        cookie, 
        videoIdForRef,
        oid
      );

      return { content: [{ type: "text", text: markdownResponse }] };
    } catch (error) {
      // 统一处理流程中发生的任何错误
      return { content: [{ type: "text", text: `❌ 获取评论失败: ${error.message}` }] };
    }
  }

  /**
   * 格式化单条评论的显示内容。
   * @param {object} comment - 单条评论的数据对象。
   * @returns {string} - 格式化后的 Markdown 字符串。
   */
  _formatSingleCommentContent(comment) {
    const timeStr = new Date(comment.ctime * 1000).toLocaleString('zh-CN', { hour12: false });
    const userLevel = comment.member.level_info?.current_level || 0;
    
    let md = `**👤 ${comment.member.uname}** (Lv.${userLevel}) | 👍 ${comment.like} | 🕐 ${timeStr}\n`;
    md += `> ${comment.content.message.replace(/\n/g, '\n> ')}\n`;
    return md;
  }

  /**
   * 生成最终返回给用户的 Markdown 格式报告。
   * @param {object} pageInfo - B 站 API 返回的页面数据。
   * @param {boolean} includeReplies - 是否包含楼中楼回复。
   * @param {string} cookie - 用户 Cookie。
   * @param {string} videoId - 视频 ID。
   * @param {number} oid - 视频 aid。
   * @returns {Promise<string>} - 完整的 Markdown 报告。
   */
  async generateMarkdownResponse(pageInfo, includeReplies, cookie, videoId, oid) {
    const currentPage = pageInfo.page?.num || 1;
    const totalCount = pageInfo.page?.count || 0;
    const pageSize = pageInfo.page?.size || 20;
    const totalPages = pageSize > 0 ? Math.ceil(totalCount / pageSize) : 1;

    let md = `## 📺 B 站评论分析结果\n\n`;
    md += `📄 **当前显示**: 第 ${currentPage} / ${totalPages} 页\n`;
    md += `📊 **评论总数**: ${totalCount} 条\n\n`;

    const allComments = [...(pageInfo.hots || []), ...(pageInfo.replies || [])];

    if (allComments.length === 0) {
      md += "😴 **此页面没有评论。**\n\n";
      md += "✅ 分析完成。如果视频有更多评论，请尝试请求其他页面。";
      return md;
    }
    
    const limit = simplePool(5); // 并发控制器，同一时间最多发送 5 个请求

    const replyTasks = includeReplies 
      ? allComments.map(comment => {
          if (comment.rcount > 0) {
            return limit(() => this.bilibiliAPI.fetchReplies(oid, comment.rpid, cookie, videoId));
          }
          return Promise.resolve([]);
        })
      : allComments.map(() => Promise.resolve([]));
    
    const allReplies = await Promise.all(replyTasks);

    const commentWithReplies = allComments.map((comment, index) => ({
      comment,
      replies: allReplies[index] || []
    }));

    md += "### 💬 评论列表\n";
    commentWithReplies.forEach(item => {
        md += this.formatCommentWithReplies(item.comment, item.replies);
    });

    md += "---\n\n";
    md += `✅ **成功加载第 ${currentPage} 页的评论。**\n`;
    if (currentPage < totalPages) {
      md += `💡 如需浏览下一页 (第 ${currentPage + 1} 页), 请在下次请求时指定 \`page: ${currentPage + 1}\`。`;
    } else {
      md += `🏁 已到达最后一页。`;
    }

    return md;
  }

  /**
   * 格式化包含楼中楼回复的完整评论区块。
   * @param {object} comment - 主评论数据。
   * @param {Array<any>|'fetch_failed'} replies - 楼中楼回复数据或失败标识。
   * @returns {string} - 格式化后的 Markdown 字符串。
   */
  formatCommentWithReplies(comment, replies) {
    let md = this._formatSingleCommentContent(comment);

    if (replies === 'fetch_failed') {
      md += `  ↳ ⚠️ *此评论的楼中楼回复加载失败，请稍后重试。*\n`;
    } else if (replies.length > 0) {
      md += `\n**📝 楼中楼回复** (共 ${comment.rcount} 条，显示前 ${replies.length} 条):\n`;
      replies.forEach(reply => {
        const replyTime = new Date(reply.ctime * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        md += `  ↳ **${reply.member.uname}**: ${reply.content.message} *(👍${reply.like} | ${replyTime})*\n`;
      });
      if (comment.rcount > replies.length) {
        md += `  ↳ *...还有 ${comment.rcount - replies.length} 条回复*\n`;
      }
    }
    
    md += "\n---\n\n";
    return md;
  }

  /**
   * 启动 MCP 服务器并监听传入的请求。
   */
  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    // 添加版本信息到启动日志
    console.error("🚀 Bilibili 评论工具已启动 (v1.0.0)");
    console.error(`🔍 环境变量检查: BILIBILI_COOKIE - ${process.env.BILIBILI_COOKIE ? '✅ 已设置' : '❌ 未设置'}`);
  }
}

// 实例化并启动服务器
const server = new BilibiliMCPServer();
server.run().catch((error) => {
  console.error("❌ 服务器启动失败:", error);
  process.exit(1);
});