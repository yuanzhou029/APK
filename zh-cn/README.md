# Home Assistant 多语言翻译合并工具

这是一个用于合并 Home Assistant 前端翻译文件的 Python 脚本。它会自动扫描 `translations` 目录中指定语言的所有翻译文件（如 `zh-Hans-*.json`、`zh-Hant-*.json`、`fr-*.json` 等），并将它们合并为一个与 `en.json` 结构完全相同的完整语言包（如 `zh.json`、`fr.json`）。

## 功能特性

- ✅ **多语言支持**：支持任意语言代码（zh-Hans, zh-Hant, fr, de, es 等）
- ✅ **自动扫描**：自动查找指定语言的所有翻译文件
- ✅ **智能合并**：正确处理重复键，后读取的文件覆盖先读取的文件
- ✅ **结构保持**：生成的翻译文件与 `en.json` 嵌套结构完全一致
- ✅ **缺失处理**：未翻译的键值保留英文原文
- ✅ **结构验证**：自动验证生成文件的结构一致性
- ✅ **详细报告**：生成包含模块分类的翻译覆盖率统计
- ✅ **支持命令行**：可指定工作目录和语言代码，提供详细帮助信息
- ✅ **模块化设计**：代码结构清晰，易于扩展和维护

## 文件结构要求

脚本期望的工作目录结构：

```
工作目录/
├── en.json                    # 英文源语言包
├── translations/              # 翻译文件目录
│   ├── {语言代码}-*.json      # 根目录翻译文件 (如 zh-Hans-*.json)
│   ├── app/                   # 应用模块翻译
│   │   └── {语言代码}-*.json
│   ├── config/                # 设置模块翻译
│   │   └── {语言代码}-*.json
│   ├── home/                  # 主页模块翻译
│   │   └── {语言代码}-*.json
│   └── ...其他模块目录
└── merge_translations.py      # 本脚本
```

**注意**：翻译文件通常以 `{语言代码}-{哈希值}.json` 格式命名，如 `zh-Hans-8ea3254e41361a7a801a38960962c374.json`。

## 环境要求

- Python 3.6 或更高版本
- 不需要额外依赖库

## 安装和使用

### 1. 基本使用 (简体中文)

将脚本放在包含 `en.json` 和 `translations` 目录的工作目录中，然后运行：

```bash
# 合并简体中文翻译 (默认)
python merge_translations.py
```

### 2. 合并其他语言

```bash
# 合并繁体中文翻译
python merge_translations.py --lang zh-Hant

# 合并法语翻译
python merge_translations.py --lang fr

# 合并德语翻译  
python merge_translations.py --lang de

# 合并西班牙语翻译
python merge_translations.py --lang es
```

### 3. 指定工作目录

如果脚本不在目标目录中，可以指定工作目录：

```bash
# 合并指定目录的德语翻译
python merge_translations.py --dir /path/to/your/translations --lang de
```

或者使用短选项：

```bash
python merge_translations.py -d /path/to/translations -l de
```

### 4. 查看帮助信息

```bash
python merge_translations.py --help
```

## 输出文件

脚本运行后会生成以下文件：

### 1. `{语言代码}.json`
完整的翻译语言包，结构与 `en.json` 完全相同。所有已翻译的内容显示为目标语言，未翻译的内容保留英文原文。

**文件名规则**：
- `zh-Hans` → `zh.json` (取连字符前的部分)
- `zh-Hant` → `zh.json`
- `fr` → `fr.json`
- `de` → `de.json`

**示例对比**：
```json
// en.json
{
  "panel": {
    "demo": "Demo",
    "apps": "Apps"
  }
}

// zh.json (简体中文)
{
  "panel": {
    "demo": "演示",
    "apps": "应用"
  }
}

// fr.json (法语)
{
  "panel": {
    "demo": "Démo",
    "apps": "Applications"
  }
}
```

### 2. `missing_translations.txt`
缺失翻译的完整列表，按模块分类排序。包含详细的统计信息，可用于后续补充翻译。

**格式：**
```
缺失翻译列表 (zh-Hant):
===========================================================
总计: 184 个缺失翻译
英文源键数: 7723
翻译覆盖率: 97.62%
===========================================================

[ui.panel] - 103 个:
----------------------------------------
ui.panel.config.automation.dialog_new.no_blueprints_match_search
ui.panel.config.automation.editor.generic
ui.panel.config.matter.device_actions.manage_lock
...

[ui.dialogs] - 47 个:
----------------------------------------
ui.dialogs.voice_command.show_details
ui.dialogs.date-picker.title
ui.dialogs.more_info_control.edit_domain.automation
...
```

### 3. 控制台输出
运行过程中会显示详细的处理进度和统计信息：

```
[INFO] 开始 zh-Hant 翻译合并处理
[INFO] 工作目录: /path/to/translations
[INFO] 目标语言: zh-Hant
[INFO] 输出文件: zh.json
[INFO] 找到 17 个 zh-Hant-*.json 文件
[INFO] 处理文件 [1/17]: translations\zh-Hant-*.json - 2334 个翻译
...
[INFO] 翻译合并报告
===========================================================
[INFO] 统计信息:
[INFO]   - 英文源键数 (en.json): 7,723
[INFO]   - zh-Hant 翻译键数: 8,409
[INFO]   - 成功匹配键数: 7,539
[INFO]   - 缺失匹配键数: 184
[INFO]   - 翻译覆盖率: 97.62%
[INFO]   - 处理文件数: 17/17
[INFO]   - 重复键数: 0

[INFO] 缺失翻译按模块分布 (共 184 个):
[INFO]   - ui.panel: 103 个 (56.0%)
[INFO]       * ui.panel.config.automation.dialog_new.no_blueprints_match_search
[INFO]       * ui.panel.config.automation.editor.generic
[INFO]       * ui.panel.config.matter.device_actions.manage_lock
[INFO]   - ui.dialogs:  47 个 (25.5%)
[INFO]       * ui.dialogs.voice_command.show_details
[INFO]       * ui.dialogs.date-picker.title
[INFO]       * ui.dialogs.more_info_control.edit_domain.automation
[INFO]   - landing-page:  28 个 (15.2%)
[INFO]   - 其他 3 个模块: 6 个 (3.3%)

[INFO] 缺失翻译示例 (前20个):
[INFO]     1. ui.card.valve.position
[INFO]     2. ui.components.date-range-picker.time_from
[INFO]     3. ui.components.date-range-picker.time_to
[INFO]   ...
[INFO] 完整缺失列表已保存到: /path/to/translations/missing_translations.txt
===========================================================
[INFO] 处理完成!
```

## 处理流程

脚本按照以下步骤执行：

1. **扫描文件**：查找指定语言的所有翻译文件（如 `zh-Hant-*.json`）
2. **提取翻译**：读取所有翻译文件，合并为扁平化的键值对字典
3. **分析结构**：读取 `en.json` 分析其嵌套结构，收集所有叶节点键路径
4. **重建结构**：以 `en.json` 为模板，为每个键查找目标语言翻译，重建嵌套结构
5. **保存文件**：保存生成的翻译文件（如 `zh.json`）
6. **结构验证**：比较翻译文件和 `en.json` 的结构一致性
7. **生成报告**：统计翻译覆盖率，按模块分类分析缺失翻译，生成详细报告

## 翻译优先级规则

当同一个键出现在多个翻译文件中时，按以下顺序决定优先级：

1. **子目录文件** 优先级高于 **父目录文件**
2. **后读取的文件** 优先级高于 **先读取的文件**

例如：
- `translations/config/zh-Hans-*.json` 覆盖 `translations/zh-Hans-*.json` 中的相同键
- 按目录深度排序，确保更具体的模块翻译覆盖通用翻译

## 常见问题

### Q: 运行脚本时出现编码错误

**A**: 这通常是因为 Windows 控制台的编码问题。可以尝试以下方法：

```bash
# 方法1: 设置环境变量
set PYTHONIOENCODING=utf-8
chcp 65001
python merge_translations.py

# 方法2: 重定向输出到文件
python merge_translations.py > output.log 2>&1
```

### Q: 如何检查生成的 `zh.json` 是否正确？

**A**: 可以使用以下方法验证：

1. **结构对比**：脚本会自动验证结构一致性
2. **文件大小**：`zh.json` 和 `en.json` 应该大小相近（约 500KB）
3. **关键翻译**：检查几个关键翻译是否正确，如：
   ```bash
   python -c "import json; data=json.load(open('zh.json')); print(data['panel']['demo'])"
   ```
   应该输出：`演示`

### Q: 如何补充缺失的翻译？

**A**: 有两种方法：

1. **直接编辑翻译文件**：在对应的 `translations/模块目录/zh-Hans-*.json` 中添加缺失的键值对
2. **更新翻译源**：从 Home Assistant 官方获取最新的翻译文件，重新运行脚本

### Q: 脚本可以用于其他语言吗？

**A**: 可以，但需要修改脚本中的文件匹配模式。目前硬编码为 `zh-Hans-*.json`，如果要处理其他语言，需要修改脚本第 73 行的文件查找模式。

## 高级用法

### 1. 批量处理多个语言

```bash
# 批量处理多个语言的翻译
for lang in zh-Hans zh-Hant fr de es; do
    echo "处理语言: $lang"
    python merge_translations.py --lang "$lang"
    echo ""
done
```

### 2. 批量处理多个目录和语言

```bash
# 批量处理多个 Home Assistant 版本和语言的翻译
for version in v1.0 v2.0 v3.0; do
    for lang in zh-Hans zh-Hant; do
        echo "处理版本: $version, 语言: $lang"
        python merge_translations.py --dir "/path/to/$version" --lang "$lang"
        echo ""
    done
done
```

### 3. 集成到构建流程

```bash
# 在 Home Assistant 前端构建过程中自动生成多语言翻译
cd home-assistant-frontend
for lang in zh-Hans zh-Hant fr; do
    python merge_translations.py --lang "$lang"
    # 根据语言代码生成输出文件名
    if [[ "$lang" == zh-Hans ]]; then output="zh.json"; fi
    if [[ "$lang" == zh-Hant ]]; then output="zh-Hant.json"; fi
    if [[ "$lang" == fr ]]; then output="fr.json"; fi
    cp "$output" "dist/translations/"
done
```

### 4. 监控翻译覆盖率

```bash
# 提取覆盖率数据用于监控
python merge_translations.py --lang zh-Hant 2>&1 | grep -A5 "统计信息:"

# 提取详细的缺失模块分布
python merge_translations.py --lang fr 2>&1 | grep -A10 "缺失翻译按模块分布"

# 保存统计信息到文件
python merge_translations.py --lang de 2>&1 | tee de-translation.log
```

## 更新日志

### v1.1 (增强版)
- **多语言支持**：支持任意语言代码（zh-Hans, zh-Hant, fr, de, es 等）
- **改进的统计信息**：清晰对比英文源键数和翻译键数
- **模块化分类**：缺失翻译按模块分类统计和展示
- **详细报告**：包含模块分布的翻译覆盖率报告
- **模块化设计**：代码重构，易于维护和扩展
- **改进的用户体验**：更清晰的命令行帮助和输出信息

### v1.0 (初始版本)
- 基础功能：扫描、合并、重建、验证
- 支持命令行参数
- 生成详细报告

## 技术支持

如果遇到问题，请：

1. 检查工作目录结构是否正确
2. 查看控制台输出的错误信息
3. 确保 Python 版本符合要求
4. 检查文件编码是否为 UTF-8

## 许可证

本脚本基于 MIT 许可证开源，可以自由使用、修改和分发。