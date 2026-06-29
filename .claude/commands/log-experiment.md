# /log-experiment

记录最近一次实验。永远不要跳过——失败与成功同样有价值。

## 选择文件夹

列出 `experiments/exp_*/`。设 `N` = 最大编号。
- 如果 `exp_N/plan.md` 存在但 `result.md` 不存在 → 使用 `exp_N/`。
- 否则 → 创建 `exp_(N+1)/`。
- 还没有任何文件夹 → `exp_1/`。

永远不要覆盖已有的 `result.md`。如果需要覆盖，停下来询问用户。

## 写入产物

1. 将 `solution/model_new.py` 复制到该文件夹（保持同名）。
2. 将 `scripts/output/bench_latest.log` 复制到该文件夹的 `bench.log`。
3. 如果 `scripts/output/profile_latest.txt` 存在，复制到该文件夹的 `profile.txt`。
4. 编写 `result.md`：

```markdown
# 实验 N — YYYY-MM-DD

**描述：** 改了什么、为什么改。在实施方案时引用 `plan.md`。

## 结果
- 正确性：通过 / 失败（最大误差：X.XXe-X）
- Model 延迟：X.XXX ms
- ModelNew 延迟：X.XXX ms
- Model (compiled) 延迟：X.XXX ms
- 加速比 (new/base)：X.XXx
- 加速比 (compile/base)：X.XXx
- 模式：quick | full

## 经验总结
学到了什么。接下来该尝试什么或避免什么。如果是跨实验的持久性洞察，同时在 `experiments/LESSONS.md` 追加一行。
```

5. 追加到 `experiments/summary.md`（如果不存在则先创建含表头行）：

```markdown
| 实验 | 日期 | 描述 | ModelNew 延迟 | 加速比 | 正确性 | 备注 |
|---|---|---|---|---|---|---|
| N | YYYY-MM-DD | 一句话描述 | X.XXX ms | X.XXx | ✅/❌ | Δ% 相对前最优，"新最优" / "回退" / "消融" |
```

`备注` 列保持简洁。详细内容放在 `result.md` 中。
