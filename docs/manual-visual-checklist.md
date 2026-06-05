# Manual Visual Checklist — Layer 4B

御主 2026-06-04 09:35 SGT mandate: 自动化覆盖 8 milestone 工程链路（Layer 3 + Layer 4A），人眼负责 UI 视觉 / 文案清晰度 / 体验流畅度。本 checklist 是 v1.0 release-candidate 的人工验收清单——主要给最终决策 sign-off 用，截图建议位置标在每项后。

**前置条件**：
- 自动化测试（Layer 1 + 2 + 3 + 4A）全 PASS
- Dev server 在 `http://localhost:5173`，`--scenario liuchao` 启动
- sample-overhaul mod 已放 `$CWS_DATA_DIR/mods/`
- LLM key 已配（要看 Layer 4 LLM 部分）

---

## 1. UI 布局合理性

打开 `http://localhost:5173` → 默认游戏页面，肉眼检查：

- [ ] **顶部栏 / 主面板**：scenario badge（"📜 六朝纪事"）有合适位置，不挤压其他 UI 元素
  - 📸 建议截图：默认页面整体
- [ ] **系统菜单**：Mod Manager / Scenario Browser / Settings 三个入口都清晰可达，没有藏在二级菜单深处
  - 📸 建议截图：系统菜单展开状态
- [ ] **窗口 resize**：把浏览器从 1920x1080 缩到 1280x720（笔记本常见），核心 UI 不溢出
- [ ] **暗色 / 亮色**（如果有）：scenario badge + Python hooks badge 在两种主题下都可读

## 2. Warning 文案清晰度

### 2.1 Hot-swap warning（v0.8）

打开 Settings → "Advanced runtime control" 开关 → 进入 game → 点击 scenario badge → "Activate" → 选 "hot-swap" mode → 弹 confirm modal

- [ ] 警告文案完整显示 verbatim：**"Hot-swap does not re-anchor time. Events scheduled before the current world time will not fire."**
- [ ] 中文本地化（如有）翻译准确，不丢失"不会触发"的关键语义
- [ ] modal 不被截断，按钮（取消 / 确认）位置清晰
- [ ] 翻译完成度：5 个 locale (zh-CN / zh-TW / en-US / ja-JP / vi-VN) 都覆盖
- 📸 建议截图：hot-swap confirm modal 全貌

### 2.2 Python hooks trust warning（v1.0）

Settings → "Allow trusted Python mods" 开关 → 弹 trust warning modal

- [ ] 警告核心信息显示：**"Untrusted mods can do anything the game can do"**（或本地化变体）
- [ ] 用户明白这是"会执行任意 Python 代码"，不是普通设置开关
- [ ] modal 按钮文案：Continue / Cancel 等清晰，不引导用户盲点 OK
- 📸 建议截图：Python toggle confirm modal

### 2.3 Conflict modals（v0.6 + v1.0）

模拟两个同名 mod 触发 conflict：（需要手动创建第二个 sample mod）

- [ ] 冲突 modal 列出冲突项（哪个 predicate / asset 冲突）
- [ ] 选项清晰：overwrite / rename / cancel
- 📸 建议截图：conflict modal 列出冲突时

## 3. Scenario / Mod 面板易懂性

### 3.1 ScenarioBrowserModal（v0.9）

打开 Scenario Browser

- [ ] 三个 tab（Installed / Downloaded / Updates）切换明确
- [ ] 每张 scenario card 信息密度合理：title + version + author + description + tags + fingerprint badge
- [ ] Source badge "Bundled" vs "Installed" 区分明显
- [ ] Verification badge（✓ verified / ⚠ modified / ○ unsigned）有视觉差异（颜色 / icon）
- [ ] Per-row 按钮（Export / Remove / Update）符合用户期待
- 📸 建议截图：Scenario Browser 三 tab 各一张

### 3.2 ScenarioOverviewModal（v0.3）

启动后点击 scenario badge

- [ ] 标题 / 版本 / 描述 / world_background 排版清楚
- [ ] "已触发事件" / "未触发事件" 分组明显（颜色 / 加粗）
- [ ] 当前接管 NPC（controlled_avatar）标识清楚
- [ ] Debug tab（advanced mode on）出现，显示 vars + dispatch log + triggered events
- 📸 建议截图：ScenarioOverviewModal main view + Debug tab

### 3.3 ModManagerModal（v1.0）

打开 Mod Manager

- [ ] 4 tab（Installed / Downloaded / Load Order / Extensions）功能明确，玩家能直觉理解
- [ ] Mod card：name + version + author + fingerprint + extensions list + Python badge
- [ ] **"Python hooks: disabled" vs "Python hooks: enabled" badge 视觉差异明显**（这是 safety gate 的视觉表达）
- [ ] Load Order tab 拖拽 reorder 可用（拖一个上下试试）
- [ ] Extensions tab 列出 active extensions（asset / LLM / locale / predicate / effect / hook）
- 📸 建议截图：Mod Manager 四 tab 各一张 + Python gate ON/OFF 对比

### 3.4 ScenarioWizardModal（v0.7）

ScenarioBrowserModal → "Create Scenario" 按钮

- [ ] 6 步 step indicator 显示进度
- [ ] 每步表单字段标签清楚，required 字段标识明确
- [ ] "Start from Template" 下拉选项有 historical / fantasy / sandbox 三个
- [ ] Schema docs "?" 按钮点击弹出 SchemaDocsModal，内容易读
- [ ] "Save & Activate" + "Export .zip" 两个出口都清晰
- 📸 建议截图：Wizard 步骤 1 + 步骤 3 LLM Assisted（带 LLM key）+ 步骤 6 Review

## 4. LLM authoring 质量（如 LLM key 已配）

Wizard step 3 LLM Assisted → 输入描述 → Generate

测试描述（御主可换）：
> "A short scenario set in a small mountain village. Three main characters: a wise elder, a brave young hunter, and a mysterious wanderer. They face a flood that threatens the village."

- [ ] Generate 后 wizard 表单字段大部分自动填充：scenario_id / title / description / world_background / 3 个 avatar
- [ ] LLM 输出的 avatar names / personas 与描述一致（不是 hallucinated 完全 unrelated）
- [ ] 至少 3-5 个 timeline event 生成
- [ ] Validation errors（如有）显示清楚，user 知道哪里要修
- [ ] 一次生成 cost 在 30 秒内（合理）
- 📸 建议截图：Generate 前 / Generate 后 wizard step 4 + step 5 对比

## 5. 端到端流畅度

走一遍完整路径，主观打分（1-5 分，3 分及格）：

- 新玩家从 boot 到选 scenario 开始游戏：____ 分
  - 评注：____
- 创作者从 wizard 创建 scenario → 导出 .zip → 重新导入验证：____ 分
  - 评注：____
- mod 用户从安装 mod → 启用 Python gate → 看到 mod 效果：____ 分
  - 评注：____
- mod 创作者从 examples/mods/sample-overhaul/ 起步制作自己的 mod：____ 分
  - 评注：____

## 6. 已知限制 / TODO

记录人工测试中发现的、但不阻塞 v1.0 ship 的 polish 项：

- [ ] ______________________
- [ ] ______________________
- [ ] ______________________

---

## Sign-off

- [ ] 1+2+3 全部通过 → v1.0 release-candidate 视觉合格
- [ ] 4 LLM 部分（如适用）→ LLM authoring 质量可接受
- [ ] 5 流畅度评分平均 ≥ 3 → 用户体验过关
- [ ] 6 已知限制 → 任何 release-blocker 项额外标 🔴，其余 polish 项可作 v1.1 backlog

御主签字：________________  日期：________________
