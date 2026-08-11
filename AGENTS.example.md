# Sports Eval Core · AI 协作规则示例

将本文件复制为 `AGENTS.md` 后，可作为支持该约定的 AI Harness 的仓库级规则。

1. 个人数据任务只读本地输入，不联网、不上传。
2. 先运行 `scripts/coach_core.py context`，不要自行扫描或拼接私人数据目录。
3. 只输出 Response v2；每条关键观察必须包含 `source/pointer/layer/observed_value`。
4. 回答展示前运行 `scripts/coach_core.py validate`；失败不得绕过。
5. 实验层不能单独触发训练处方；红黄灯不得由模型降级。
6. 训练计划变更必须等待使用者明确确认。
7. 公开贡献只能使用 `synthetic: true` 的人工合成数据。
