# AI 编程比赛赛前准备清单

## 你这台电脑当前状态

- Python: 已安装，当前为 `Python 3.14.2`，满足赛方要求的 `Python 3.10+`。
- pip: 已可用，跟随 Python 3.14。
- Node.js: 已安装，当前为 `v24.13.0`，满足赛方要求的 `Node.js 18+`。
- npm: 已可用，当前为 `11.6.2`。
- git: 已安装，当前为 `git version 2.54.0.windows.1`。
- git 提交身份: 已配置。
  - user.name: `LilPolaris`
  - user.email: `3091974289@qq.com`
- Claude Code: 已安装，当前为 `2.1.126`。
- OpenAI Codex: 桌面版可用；命令行 `codex --version` 在当前终端里提示拒绝访问，但这不影响你现在使用 Codex 桌面。
- GitHub CLI `gh`: 已安装，当前为 `2.92.0`；当前终端暂时没刷新 PATH，重开终端后通常可直接使用 `gh`。

## 赛前必须完成

- 注册并能登录 GitHub 账号。
- 注册并能登录魔搭 ModelScope 账号。
- 下载赛方提供的 7 本教材 PDF 到本地，最好单独放一个文件夹。
- 确认比赛通知群、赛题发布位置、提交方式都能正常打开。
- 比赛开始前 30 分钟阅读赛题文档，先找“提交要求”“评分标准”“必须实现功能”。

## 建议额外准备

- 重开终端后运行 `gh --version`，确认 GitHub CLI 可直接使用。
- 在 GitHub 网站上提前创建一个空测试仓库，练习一次上传代码。
- 准备一个比赛专用文件夹，例如 `D:\AI_Competition`，避免文件乱放。
- 把 7 本 PDF、赛题文档、代码项目放在同一个大文件夹下面。
- 比赛时优先保证能运行、能提交，再追求功能完整和界面好看。

## 比赛时推荐节奏

- 0-30 分钟: 读题，确认提交要求，列功能优先级。
- 30-90 分钟: 先做最小可运行版本，不追求完美。
- 90-120 分钟: 补核心功能，保证演示流程顺。
- 第 2 小时: 按群内通知提交 GitHub 链接，拿 AI 评审建议。
- 120-240 分钟: 根据建议修最高收益的问题。
- 最后 60 分钟: 测试、截图、写 README、确认提交链接可访问。

## 常用命令速查

检查环境:

```powershell
python --version
node --version
git --version
npm --version
```

进入项目文件夹:

```powershell
cd 路径
```

安装前端依赖:

```powershell
npm install
```

启动前端项目，具体命令看赛题或项目里的 `package.json`:

```powershell
npm run dev
```

查看 git 状态:

```powershell
git status
```

保存一次代码记录:

```powershell
git add .
git commit -m "update competition project"
```

推送到 GitHub:

```powershell
git push
```

## 小白比赛策略

- 先让项目跑起来，这是第一优先级。
- 每做完一个功能就保存一次 git commit。
- 不懂报错时，把完整报错发给 AI，不要只说“坏了”。
- 让 AI 改代码前，先让它读项目结构和 README。
- 比赛后半段不要大改架构，集中修能拿分的明显问题。
