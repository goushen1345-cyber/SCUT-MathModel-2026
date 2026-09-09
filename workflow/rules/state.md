# 状态协议与脚本使用

脚本仅用 Python 3 标准库。路径示例从仓库根目录执行；用户无需手动维护 JSON。Agent 用 apply_patch 编写候选状态，再由脚本检查提交，不能绕开脚本直接改正式 state.json。脚本是可靠性辅助，不是真实消息认证或文件权限隔离。

## 初始化与读取

```text
python workflow/scripts/statectl.py init projects/练习 --questions Q1 Q2 Q3
python workflow/scripts/statectl.py validate projects/练习
python workflow/scripts/statectl.py view projects/练习
```

init 只创建空项目状态和三本人类账本，不读取/改动培训作业，不代表任何研究通过。已有 state.json 拒绝覆盖。题号、CORE角色、依赖及项目研究顺序在全局题意确认时明确；依赖必须无环。

## 状态提交

```text
python workflow/scripts/statectl.py commit projects/练习 --candidate projects/练习/state/proposed.json
```

Agent 先读取当前 revision，以它加一生成候选，变更依据写 history；用户授权必须来自真实消息。commit 检查修订号、状态转换、必要授权、依赖、冻结快照，成功后原子替换 state.json 并生成 state.md；失败不变更正式 JSON。state.md 可通过 view 重建。锁冲突先调查，不自动删除锁。

stage 正常路线：GLOBAL → WAIT_G0 → DATA_PLAN → WAIT_G1 → DATA_EXEC → WAIT_G2 → READY → CANDIDATES → WAIT_A → TRIAL → WAIT_B → DEEPEN_PLAN → WAIT_C → DEEPEN → WAIT_D → FROZEN →（进入获批下一问）CANDIDATES。FROZEN → PAPER_PLAN → WAIT_P → PAPER → WAIT_FINAL → DONE。

WAIT_D 可经人工授权回 DEEPEN_PLAN 或 CANDIDATES；FROZEN 可经人工授权重开，旧快照保留，标记所有依赖后代 validity=STALE。DATA/协议变更同样需要人工影响决定；不能清除历史，不能仅因重新生成文件而标恢复有效。

数据回访：研究、READY 或论文未完成阶段可经 GLOBAL 范围的真实批准返回 DATA_PLAN，同时 active_question 清空，history 记录原位置。再经过 G1/G2；data_version 改变时既有研究必须标 STALE。回到 READY 后，用户指定重开哪问并批准影响范围，再进入 CANDIDATES；旧快照不删。若不改数据版本，也不能无授权自行返回原研究。

## 字段

state.json 含 schema_version、revision、stage、execution_status、active_question、data_version、questions、pending_gate、authorizations、history、blockers。每问含 role、status、validity、depends_on、frozen_version、snapshots。依赖指定 question+version，初始化未冻结的版本可为 null，但进入本问时必须绑定有效冻结版本。

WAIT 阶段 pending_gate 必须含 id、plan_version、scope、summary、allowed_actions、budget、stop_condition；scope 为 GLOBAL、PAPER 或对应 Qk。批准后清空 pending_gate，authorizations 追加而不改历史。

授权条目含 id、from_stage、to_stage、scope、plan_version、user_quote、message_ref、confirmed_by。confirmed_by 必须是 user，但脚本不能证明真实性；Agent必须核实对话。进入/重开等非WAIT转换同样需要授权条目，其 plan_version 指向已向用户解释的进入/重开方案。

history 每次至少追加一条，说明为何变更、产物及授权ID。执行状态 ACTIVE / WAITING / BLOCKED / DONE。blockers 非空则只能 BLOCKED，保持原阶段；解决后记录证据才恢复。冻结 status=FROZEN、validity=VALID、frozen_version 指向 snapshots 键。

每份 snapshot 是 {"相对项目路径": "sha256"}，应覆盖数据/协议引用、代码、配置、结果、验证和论文证据；项目内路径不得越界。冻结文件不可覆盖，脚本核验有效冻结快照哈希；旧失效版本仍保留记录。没有实际产物不得填虚构哈希。freeze 不能改变 active_question；进入另一问是下一次独立提交，即使同一用户消息已授权两项操作。

所有必要问冻结有效后才允许 PAPER_PLAN。故事线 WAIT_P 必須人工批准，最后 WAIT_FINAL 批准只表示版本确认，不授权上传。

## 人工语义检查仍不可省略

程序不能证明一条 user_quote 的语义构成批准，不能验证预算执行、统计正确性、产物类型齐全、数据版本标签真实性或创新。由 Agent 依据真实消息和研究证据核实。直接改权限相同的文件仍可绕过；不声称绝对 HARD GATE。
