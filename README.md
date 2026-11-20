<h1 align="center">源显公司个人月报</h1>

<p align="center"><em>把零散工作记成可追溯的日记，再整理成点、线、面月报。</em></p>

<p align="center">
  <a href="https://github.com/AIHongDOU"><img src="https://avatars.githubusercontent.com/u/314199668?v=4&amp;s=120" width="96" height="96" alt="AIHongDOU 的 GitHub 头像"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Codex-Skill-2f81f7?style=flat-square" alt="Codex Skill">
  <img src="https://img.shields.io/badge/WorkBuddy%20%7C%20TRAE-ready-2f81f7?style=flat-square" alt="WorkBuddy and TRAE">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3fb950?style=flat-square" alt="Python 3.9 or newer">
  <img src="https://img.shields.io/badge/%E6%95%B0%E6%8D%AE-%E6%9C%AC%E5%9C%B0%E4%BF%9D%E5%AD%98-3fb950?style=flat-square" alt="Local data">
</p>

---

月底才开始写月报，往往要重新翻聊天、笔记和工单：哪些已经完成，哪些还要复测，数字是否重复计算，原计划又写了什么？

这个技能把每件工作先保存到本地台账。日记保留日期、来源和状态；月末再按**点、线、面**整理，每类最多五项，并用模板生成 Excel 草稿。你可以核对、修改、定稿，发送邮件前还会看到收件人和附件预览。

## 它怎么干活

<p align="center"><img src="docs/images/workflow.svg" width="860" alt="工作日记、去重核对、点线面月报流程"></p>

```text
你：今天修复了设备列表重复显示，筛选和刷新都回归通过。
→ 日记：记录事项、来源、日期和“已验证”状态。

你：用这个月的日记生成月报。
→ 月报：合并同一问题的多次进展，核对数量，整理点、线、面总结。
→ 交付：保留原始明细，生成可检查的 Excel 草稿。
```

```mermaid
flowchart LR
    A[工作对话或手记] --> B[本地工作日记与台账]
    B --> C[去重、核对与关联原计划]
    C --> D[点、线、面月报草稿]
    D --> E[人工核对与定稿]
    E --> F[员工自行上传钉钉或确认邮件发送]
```

## 能做什么

| 场景 | 结果 |
| --- | --- |
| 每天记一件事 | 保存原话、日期、来源、分类、结果和待办，可随时修正 |
| 个人工作日记 | Codex 可汇总本人工作对话；WorkBuddy 可定时整理指定工作区内的本人笔记和对话导出，生成可复制的日报正文 |
| 整理整月笔记 | 合并重复进展，按点、线、面形成总结，原始明细留在台账 |
| 生成月报 | 使用仓库内的 Excel 模板输出草稿，每类最多五项 |
| 核对与定稿 | 提示缺实绩、缺依据、待核分类和疑似重复；保留草稿与定稿 |
| 邮件投递 | 先预览收件人、主题和附件，员工确认后发送 |

**点**通常是独立的小事务，**线**是一天内多步骤交付，**面**是跨周或涉及多个阶段的工作。分类依据任务范围，不按 AI 实际花费的时间机械判断。

## 快速开始

在员工平时存放月报的工作区打开智能体，将下面一行粘贴进对话，让它执行安装。电脑需要 Git、Node.js（含 npx）和本仓库的读取权限。

```sh
npx --yes skills@1.9.0 add https://github.com/AIHongDOU/yuanxian-monthly/tree/main/yuanxian-monthly -a codex trae codebuddy --copy -y
```

安装后在该工作区新开对话，选择 **yuanxian-monthly（源显公司月报）** 并输入 **菜单**。支持 @ 技能的客户端可输入 `@yuanxian-monthly 菜单`；Codex 可用 `$yuanxian-monthly 菜单`，WorkBuddy 也可在对话框的技能列表选取。直接导入可下载[完整技能 ZIP](dist/yuanxian-monthly.zip?raw=1)。

菜单里选 **1 记一件事**，再补一句“今天完成了设备回归测试”；也可以一次发送 **1 今天完成了设备回归测试**。有可选回复的客户端可以点选，其余直接回复编号即可。

在支持本地文件和 Python 的智能体中打开本项目，然后直接说：

> 使用源显月报。今天完成了设备管理系统的筛选功能回归，结果通过。

月底可以说：

> 用这个月的工作日记生成我的月报，先给我草稿和核对清单。

如果要启用 Codex 个人工作日记，可在专属对话中要求每天北京时间 17:00 汇总**本人在本机 Codex 的工作对话**。定时任务需要在桌面端配置；钉钉内容由员工自行上传。

在 WorkBuddy 中，可新建每天北京时间 17:00 执行的定时任务，选择本项目作为工作区。提示词可以写成“使用源显月报，从我指定的工作笔记目录整理今天的个人工作日记，标明来源，写入我的固定日记文件”。如需纳入 Codex 对话，可将对话导出放在该目录中，也可直接复用 Codex 已生成的工作日记 TXT 整理月报。[WorkBuddy 自动化说明](https://intl.cloud.tencent.com/zh/document/product/1316/84500)

## 安装

下载或克隆本仓库，使用同一个本地项目文件夹。需要 **Python 3.9 或更高版本**；报表程序仅使用 Python 标准库。

| 平台 | 技能入口 |
| --- | --- |
| Codex | `.agents/skills/yuanxian-monthly/SKILL.md` |
| WorkBuddy | `.workbuddy/skills/yuanxian-monthly/SKILL.md`（兼容 `.codebuddy/skills/`） |
| TRAE | `.trae/skills/yuanxian-monthly/SKILL.md` |

详细安装方式、常用说法和发件环境配置见[安装与使用](安装与使用.md)。实际处理步骤见[工作手册](yuanxian-monthly/WORKFLOW.md)。

## 数据保存在本地

日记、台账、草稿和定稿默认写到项目中的 `月报数据/`。该目录已被 Git 忽略，**不会随本仓库的代码提交上传**。多人共用项目时，应分别使用各自身份目录，并由本机或共享目录权限控制访问。

邮件账号通过运行环境配置；不要把密码、授权码、工作日记或正式月报放进仓库。发送前需要预览并明确确认。

## 仓库结构

```text
.
├── README.md                 项目首页
├── 安装与使用.md             安装和日常用法
├── .agents/skills/           Codex 技能入口
├── .workbuddy/skills/        WorkBuddy 技能入口
├── .codebuddy/skills/        WorkBuddy 企业版兼容入口
├── .trae/skills/             TRAE 技能入口
└── yuanxian-monthly/
    ├── SKILL.md              技能说明
    ├── WORKFLOW.md           助手操作手册
    ├── report.py             本地请求入口
    ├── diary.py              工作日记
    ├── ledger.py             台账与核对
    ├── book.py               Excel 模板处理
    ├── compact.py            月报归并
    ├── mail_report.py        邮件预览与投递
    └── 模板_*.xlsx           月报模板
```

## 常见问题

**日记会自动发钉钉吗？** 不会。日记正文可复制，员工自行上传。

**修复次数会算成缺陷数吗？** 不会。月报按可核实的不同问题去重；缺少逐项依据时使用定性表述。

**Excel 打开时能继续记吗？** 可以。记录先留在台账，关闭 Excel 后再同步草稿。

**下月计划会自动编吗？** 不会。只写入员工提供或确认的计划。
