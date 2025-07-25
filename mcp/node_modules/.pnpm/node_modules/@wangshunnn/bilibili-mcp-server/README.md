# bilibili MCP Server

[![MIT licensed][badge-license]][url-license]
[![NPM version][badge-npm-version]][url-npm]
[![NPM Unpacked Size (with version)](https://img.shields.io/npm/unpacked-size/rolldown/latest?label=npm)][url-npm]

English | [简体中文](./README.zh-CN.md)

> _Model Context Protocol ([MCP](https://modelcontextprotocol.io/introduction)) Server for the [bilibili.com](https://www.bilibili.com) API._

<a href="https://glama.ai/mcp/servers/@wangshunnn/bilibili-mcp-server">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@wangshunnn/bilibili-mcp-server/badge" alt="bilibili Server MCP server" />
</a>

## Features

### User Info

- [x] Get user information by `mid`
- [x] Search video information by `bvid`
- [x] Search videos by keywords

## Usage

### Claude Desktop

> Refer to the official [documentation](https://modelcontextprotocol.io/quickstart/server#testing-your-server-with-claude-for-desktop-2)

config for npm (recommended)

```json
{
  "mcpServers": {
    "bilibili": {
      "command": "npx",
      "args": ["-y", "@wangshunnn/bilibili-mcp-server"]
    }
  }
}
```

_**or**_

config for local cloned repo

```json
{
  "mcpServers": {
    "bilibili": {
      "command": "node",
      "args": [
        "/ABSOLUTE/PATH/TO/PARENT/FOLDER/bilibili-mcp-server/dist/index.js"
      ]
    }
  }
}
```

Save the configuration and restart. You will see the new `bilibili MCP` option as shown below:

<div align="center">
  <img src="./assets/claude-desktop-1.png" alt="" width="500">

  <img src="./assets/claude-desktop-2.png" alt="" width="500">
  
  <img src="./assets/claude-desktop-setting.png" alt="" width="500">
</div>

#### Demo Vedio

https://github.com/user-attachments/assets/813dece6-c9b5-4bc5-96c1-c3b4d284cc76

## Local Development

1. Install dependencies

```sh
pnpm i
```

2. build

```sh
pnpm build
# or
pnpm dev
```

3. debug for local repo, see [above](#usage).

## Publishing

To publish a new version to npm:

```sh
# For patch version update (0.0.x)
pnpm publish:patch

# For minor version update (0.x.0)
pnpm publish:minor

# For major version update (x.0.0)
pnpm publish:major
```

These commands will automatically:

1. Bump the version in package.json
2. Build the project
3. Publish to npm registry

## Credits

- [bilibili-API-collect](https://socialsisteryi.github.io/bilibili-API-collect/)

[badge-license]: https://img.shields.io/badge/license-MIT-blue.svg
[url-license]: https://github.com/wangshunnn/bilibili-mcp-server/blob/main/LICENSE
[badge-npm-version]: https://img.shields.io/npm/v/@wangshunnn/bilibili-mcp-server/latest?color=brightgreen
[url-npm]: https://www.npmjs.com/package/@wangshunnn/bilibili-mcp-server