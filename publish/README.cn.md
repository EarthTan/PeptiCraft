# 已发布前端

> English version: [英文版](README.md) — 2026-10-18 的中文原版存档，英文版可能已更新。

由 `app/` 构建并复制到此处的静态单页应用。`assets/` 保存带哈希的前端脚本和样式，`data/` 保存页面所需的数据快照；`server.js` 是零依赖的 Node 静态服务器，并对未知页面路径回落到 `index.html`。

## 生成方式

内容出自前端构建，整体复制过来：

```bash
cd ../app
npm run build
cp -R dist/. ../publish/
```

这里的前端、图标和数据文件都是构建产物。本目录中没有任何内容由手工编辑：在这里做的改动会在下一次包被复制覆盖时丢失，应当改在 `../app/src/` 或 `../app/public/`，然后重新构建。

## 运行方式

```bash
node server.js
```

服务器监听 3000 端口，设置了 `PORT` 时以该值为准。它不接受其他配置，也不需要安装依赖。

## 状态

数据查询由随包提供的静态快照回答。聊天接口由 Cloudflare Pages Function 提供，因此单独运行此 Node 静态服务器时聊天功能不可用。若要启用聊天，需要部署 Pages Function 或提供兼容的后端 API。
