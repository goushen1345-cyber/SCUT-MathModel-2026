# 聊天交接：Skills 优化后继续

> 在**新聊天**第一条消息里 `@.agents/CHAT_HANDOFF.md`，并写：「按此交接继续；不要重做已完成的 skills 改动。」

## 身份与约束

- 仓库：`E:/Projects/SCUT-MathModel-2026`（国赛 C 题人机协作工作流）
- Agent 身份：Cursor Grok；遵守 `AGENTS.md`、`WORKFLOW.md`、`workflow/rules/*`
- **框架冻结**：仍是四主执行（master / problem-data / question-modeling / paper-builder）+ 独立 Reviewer + figure-support；不新增 Skill/阶段/确认点
- 改 Skills/规则 ≠ 推进赛题；不得伪造项目研究状态
- 未明确要求不要 git commit；原始材料/培训作业默认只读

## 本会话已完成

1. **第三次培训作业**（2022 C 古代玻璃）：`培训作业/第三次培训作业/` 已跑通并产出报告；曾提交并推送（历史提交，不必重做）
2. **Skills 按清单优化（文本已改完）**，P0/P1/P2 均完成：
   - **P0 人话/终检**：`cumcm-paper-builder/references/expert-paper-writing.md`（人话书面语、边界密度、偏短自检、FINAL 勾选）、`expert-abstract.md`（赛场摘要勾选）、`cumcm-paper-builder/SKILL.md`
   - **P1 竞争力**：`cumcm-question-modeling/SKILL.md`（候选配额、主张↔验证、D 创新条目）、`workflow/rules/modeling.md`（禁文末挪验证）、`cumcm-reviewer` 三档（必须处理 / 交付不达标 / **竞争力建议非阻断**）
   - **P2 口径**：`AGENTS.md`、`WORKFLOW.md`、`cumcm-master`、`cumcm-figure-support`（双重图号）、`expert-problem-data`（农例非默认题型）
3. 用户曾审阅 G0 前置稿：`projects/2024-C/paper/understanding_v2/front_matter_understanding_v2.pdf`  
   - 阶段稿约 8/10，技能对齐好；主要问题是**方法论说明书腔**（段段「因此模型需要……」、过度防御）
   - **尚未**按新人话规则重写该正文（用户可选下一步）

## 用户偏好（本会话）

- 中文、直接、短答；少加粗
- 赛场用模：高模型只用于 G0/A/B/C/D/P/Reviewer；中档写代码/EDA；低档编译排版；Ultra 订阅可留着
- 希望论文**像人写的书面语**，不要说明书腔与检查表式边界连排

## 建议下一步（任选，需用户明确授权再改研究产物）

1. 用新人话规则重写 `2024-C` 前置稿第 3 章（或整份 understanding_v2）对照腔调
2. 独立聊天开 Reviewer，用新三档审一篇已有稿
3. 若要提交本次 skills 改动：用户明确说「commit」后再提交（当前多为未提交的 `.agents` / `workflow` / `AGENTS` / `WORKFLOW` 文本变更）

## 关键路径

| 用途 | 路径 |
|------|------|
| Skills | `.agents/skills/cumcm-*/SKILL.md` |
| 论文写作细则 | `.agents/skills/cumcm-paper-builder/references/expert-paper-writing.md` |
| 规则 | `workflow/rules/{governance,chat,evidence,modeling,state}.md` |
| 2024-C 前置稿 | `projects/2024-C/paper/understanding_v2/` |
| 第三次作业 | `培训作业/第三次培训作业/` |

## 新聊天开场示例

```
@.agents/CHAT_HANDOFF.md
按交接继续。下一步请：【写清你要做的一件事】
```
