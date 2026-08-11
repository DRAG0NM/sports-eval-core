# Sports Eval Core · Obsidian 运动评估与 AI 教练内核

一个本地优先、厂商无关、可审计的个人运动与恢复趋势框架。当前公开版为 **v0.2**。

它将标准化 JSON 转换为：

- 可在 Obsidian 阅读和维护的训练日志、周报告和复盘页面；
- 原始单指标、稳健个人基线、EWMA、多维状态和变化候选；
- 带数据预算、确定性安全门和精确证据验证的模型中立 AI 教练上下文。

## 隐私与边界

- 不包含厂商账号、抓取器、私有接口或浏览器令牌逻辑；
- 不包含真实健康、睡眠、位置、训练、主观事件或个人档案；
- 示例数据全部为人工合成；
- 只用于个人趋势、教育和研究，不用于诊断、治疗或紧急决策。

完整规则见 [[PRIVACY]]、[[SECURITY]] 和 [[DISCLAIMER]]。

## 快速开始

要求 Python 3.9+，核心运行时没有第三方依赖。

```powershell
python scripts/build_report.py examples/synthetic_week.json
python scripts/coach_core.py context examples/synthetic_week.json --task daily_guidance --query "How should the synthetic plan proceed?" --output coach_context.json
python scripts/coach_core.py validate examples/synthetic_response.json coach_context.json
python -m unittest discover -s tests -p "test_*.py"
python scripts/release_audit.py
```

生成的周报告写入 `06_周报告/`。`coach_context.json` 是可再生成的临时文件，已被 `.gitignore` 排除。

## 分层设计

```text
厂商数据（仓库外）
  → 标准 weekly input
  → 原始单指标（无阈值、无加权）
  → 确定性指标（TRIMP / SRI / EF 等）
  → 实验模型（个人基线 / EWMA / 多维状态 / 变化候选）
  → Context v2 + 确定性安全门
  → 任意 AI 生成 Response v2
  → 精确 JSON Pointer、观测值、证据层与权限验证
  → 人类复核和明确确认
```

实验模型是加法层，不替换原始指标。50 是个人历史中性锚点，不是健康及格线；共享输入不构成独立生理证据。

## 目录

```text
01_数据格式/            厂商无关输入格式
02_训练日志/            人工记录模板
03_指标追踪/            趋势页模板
04_评估测试/            基线测试与复测
05_训练计划/            周期计划模板
06_周报告/              自动生成输出
07_复盘/                人工/AI 复盘模板
08_方法与边界/          指标、教练契约和使用边界
scripts/                标准库实现
schemas/                weekly input、Context v2、Response v2
examples/               仅合成示例
tests/                  算法、教练安全与隐私回归
```

入口页面：[[00_首页]]。版本变化见 [[CHANGELOG]]。

## 设计原则

1. 原始数据与公开代码分离。
2. 设备字段先归一，再计算指标。
3. 缺失数据显式降级，不填造数值。
4. 原始、确定性和实验层不得混写。
5. 安全、证据和计划权限由确定性代码执行，不交给提示词自行保证。
6. 自动生成区与用户笔记区分离；相同输入产生相同输出。

## 许可证

代码与仓库文档按 Apache License 2.0 发布，见 [[LICENSE]]。科学方法、第三方名称和引用仍归其各自权利人所有。
