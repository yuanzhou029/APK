#!/usr/bin/env python3
"""
Home Assistant 翻译合并工具
从 translations 目录中提取所有 zh-Hans-*.json 文件，
合并为与 en.json 结构相同的 zh.json 中文语言包
"""

import argparse
import json
import os
import sys
import glob
from typing import Dict, Any, List, Tuple
from collections import defaultdict
import shutil


class TranslationMerger:
    def __init__(self, base_dir: str, language_code: str = "zh-Hans"):
        """
        初始化翻译合并器
        
        Args:
            base_dir: 工作目录（包含en.json和translations目录）
            language_code: 语言代码，如 'zh-Hans', 'zh-Hant', 'fr', 'de' 等
        """
        self.base_dir = os.path.abspath(base_dir)
        self.language_code = language_code
        
        self.en_file = os.path.join(self.base_dir, "en.json")
        self.translations_dir = os.path.join(self.base_dir, "translations")
        
        # 根据语言代码生成输出文件名
        # 如果语言代码包含连字符，使用第一部分作为文件名（如zh-Hans -> zh）
        if "-" in language_code:
            output_lang = language_code.split("-")[0]
        else:
            output_lang = language_code
        self.output_file = os.path.join(self.base_dir, f"{output_lang}.json")
        
        # 统计数据
        self.stats = {
            "total_keys": 0,
            "translated_keys": 0,
            "missing_keys": 0,
            "total_files": 0,
            "processed_files": 0,
            "duplicate_keys": defaultdict(int),
        }
        
        # 存储所有扁平化翻译
        self.flat_translations: Dict[str, str] = {}
        
        # 存储缺失的翻译键
        self.missing_keys: List[str] = []
        
    def log(self, message: str):
        """输出日志信息"""
        print(f"[INFO] {message}")
    
    def warn(self, message: str):
        """输出警告信息"""
        print(f"[WARN] {message}")
    
    def error(self, message: str):
        """输出错误信息"""
        print(f"[ERROR] {message}")
    
    def find_translation_files(self) -> List[str]:
        """查找所有指定语言的翻译文件"""
        pattern = os.path.join(self.translations_dir, "**", f"{self.language_code}-*.json")
        files = glob.glob(pattern, recursive=True)
        
        if not files:
            # 尝试另一种模式：language_code.json（不带哈希后缀）
            alt_pattern = os.path.join(self.translations_dir, "**", f"{self.language_code}.json")
            files = glob.glob(alt_pattern, recursive=True)
        
        # 按目录深度排序，确保子目录文件后处理（覆盖优先级）
        files.sort(key=lambda x: (x.count(os.sep), x))
        
        self.log(f"找到 {len(files)} 个 {self.language_code}-*.json 文件")
        return files
    
    def load_json_file(self, filepath: str) -> Dict[str, Any]:
        """加载 JSON 文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.error(f"JSON 解析错误 {filepath}: {e}")
            return {}
        except Exception as e:
            self.error(f"读取文件错误 {filepath}: {e}")
            return {}
    
    def extract_flat_translations(self, files: List[str]):
        """提取并合并所有扁平化翻译"""
        self.log("开始提取扁平化翻译...")
        
        for file_idx, filepath in enumerate(files):
            self.stats["total_files"] += 1
            relative_path = os.path.relpath(filepath, self.base_dir)
            
            translations = self.load_json_file(filepath)
            if not translations:
                self.warn(f"跳过空文件或无效文件: {relative_path}")
                continue
            
            self.stats["processed_files"] += 1
            
            # 处理扁平化键值对
            for key, value in translations.items():
                if key in self.flat_translations:
                    self.stats["duplicate_keys"][key] += 1
                    self.warn(f"重复键 '{key}'，将被新值覆盖 (文件: {relative_path})")
                
                self.flat_translations[key] = value
            
            self.log(f"处理文件 [{file_idx+1}/{len(files)}]: {relative_path} - {len(translations)} 个翻译")
        
        self.log(f"合并完成: 共收集 {len(self.flat_translations)} 个唯一翻译")
    
    def analyze_en_structure(self) -> Dict[str, Any]:
        """分析 en.json 结构，收集所有叶节点键路径"""
        self.log(f"加载并分析 en.json 结构...")
        
        en_data = self.load_json_file(self.en_file)
        if not en_data:
            self.error("无法加载 en.json，退出")
            sys.exit(1)
        
        # 收集所有叶节点键路径
        leaf_keys = []
        
        def traverse(node, path_parts: List[str]):
            """递归遍历 JSON 结构"""
            if isinstance(node, dict):
                for key, value in node.items():
                    new_path = path_parts + [key]
                    traverse(value, new_path)
            elif isinstance(node, list):
                # 列表类型不常见，但处理一下
                for i, value in enumerate(node):
                    new_path = path_parts + [str(i)]
                    traverse(value, new_path)
            else:
                # 叶节点（字符串、数字、布尔值等）
                leaf_path = ".".join(path_parts)
                leaf_keys.append(leaf_path)
        
        traverse(en_data, [])
        self.stats["total_keys"] = len(leaf_keys)
        self.log(f"en.json 包含 {self.stats['total_keys']} 个叶节点键")
        
        return en_data
    
    def rebuild_translation_structure(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """以 en.json 为模板，重建嵌套结构的中文翻译"""
        self.log("开始重建嵌套结构...")
        
        def rebuild_node(node):
            """递归重建节点"""
            if isinstance(node, dict):
                result = {}
                for key, value in node.items():
                    result[key] = rebuild_node(value)
                return result
            elif isinstance(node, list):
                return [rebuild_node(item) for item in node]
            else:
                # 叶节点：尝试查找翻译
                # 注意：这里需要获取当前叶节点的完整路径
                # 但由于我们在递归中，不知道完整路径，需要重构方法
                # 改为使用单独函数处理
                return node  # 占位符，实际在外部处理
        
        # 使用新方法：遍历模板同时重建
        def rebuild_with_path(node, path_parts: List[str], result_node):
            """带路径的递归重建"""
            if isinstance(node, dict):
                for key, value in node.items():
                    new_path = path_parts + [key]
                    if isinstance(value, dict):
                        result_node[key] = {}
                        rebuild_with_path(value, new_path, result_node[key])
                    elif isinstance(value, list):
                        result_node[key] = []
                        for i, item in enumerate(value):
                            if i >= len(result_node[key]):
                                result_node[key].append(None)
                            if isinstance(item, dict):
                                result_node[key][i] = {}
                                rebuild_with_path(item, new_path + [str(i)], result_node[key][i])
                            else:
                                # 列表中的非字典项
                                result_node[key].append(rebuild_leaf(item, new_path + [str(i)]))
                    else:
                        # 叶节点
                        result_node[key] = rebuild_leaf(value, new_path)
        
        def rebuild_leaf(value, path_parts: List[str]):
            """重建叶节点，查找翻译"""
            leaf_path = ".".join(path_parts)
            
            # 查找翻译
            if leaf_path in self.flat_translations:
                self.stats["translated_keys"] += 1
                return self.flat_translations[leaf_path]
            else:
                self.stats["missing_keys"] += 1
                self.missing_keys.append(leaf_path)
                # 保留英文原文
                return value
        
        # 开始重建
        translation_data = {}
        rebuild_with_path(template, [], translation_data)
        
        return translation_data
    
    def save_translation_file(self, translated_data: Dict[str, Any]):
        """保存翻译文件"""
        output_filename = os.path.basename(self.output_file)
        self.log(f"保存 {output_filename} 到: {self.output_file}")
        
        try:
            # 使用与 en.json 相同的缩进格式
            with open(self.output_file, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(translated_data, f, ensure_ascii=False, indent=2)
            
            # 验证文件大小
            file_size = os.path.getsize(self.output_file)
            self.log(f"{output_filename} 保存成功，文件大小: {file_size:,} 字节")
            
        except Exception as e:
            self.error(f"保存 {output_filename} 失败: {e}")
            sys.exit(1)
    
    def compare_structures(self):
        """比较 en.json 和输出文件的结构"""
        output_filename = os.path.basename(self.output_file)
        self.log(f"比较 en.json 和 {output_filename} 结构...")
        
        en_data = self.load_json_file(self.en_file)
        lang_data = self.load_json_file(self.output_file)
        
        if not lang_data:
            self.error(f"无法加载 {output_filename} 进行比较")
            return
        
        def compare_nodes(en_node, lang_node, path: str = ""):
            """递归比较两个节点"""
            if type(en_node) != type(lang_node):
                output_filename = os.path.basename(self.output_file)
                self.error(f"类型不匹配 {path}: en={type(en_node).__name__}, {output_filename}={type(lang_node).__name__}")
                return False
            
            if isinstance(en_node, dict):
                # 检查键是否一致
                en_keys = set(en_node.keys())
                lang_keys = set(lang_node.keys())
                
                if en_keys != lang_keys:
                    missing_in_lang = en_keys - lang_keys
                    extra_in_lang = lang_keys - en_keys
                    
                    output_filename = os.path.basename(self.output_file)
                    if missing_in_lang:
                        self.error(f"{output_filename} 缺少键 {path}: {missing_in_lang}")
                    if extra_in_lang:
                        self.error(f"{output_filename} 多余键 {path}: {extra_in_lang}")
                    
                    return False
                
                # 递归比较所有子键
                all_match = True
                for key in en_keys:
                    new_path = f"{path}.{key}" if path else key
                    if not compare_nodes(en_node[key], lang_node[key], new_path):
                        all_match = False
                
                return all_match
            elif isinstance(en_node, list):
                if len(en_node) != len(lang_node):
                    output_filename = os.path.basename(self.output_file)
                    self.error(f"列表长度不匹配 {path}: en={len(en_node)}, {output_filename}={len(lang_node)}")
                    return False
                
                all_match = True
                for i, (en_item, lang_item) in enumerate(zip(en_node, lang_node)):
                    new_path = f"{path}[{i}]"
                    if not compare_nodes(en_item, lang_item, new_path):
                        all_match = False
                
                return all_match
            else:
                # 叶节点，允许值不同
                return True
        
        if compare_nodes(en_data, lang_data, ""):
            output_filename = os.path.basename(self.output_file)
            self.log(f"[PASS] 结构验证通过: en.json 和 {output_filename} 结构完全一致")
        else:
            output_filename = os.path.basename(self.output_file)
            self.warn(f"[WARN] 结构验证发现差异，请检查以上错误信息")
    
    def analyze_missing_by_module(self, missing_keys: List[str]) -> Dict[str, List[str]]:
        """按模块分析缺失的翻译键"""
        modules = defaultdict(list)
        
        for key in missing_keys:
            # 根据键路径分析模块
            parts = key.split('.')
            if len(parts) >= 2:
                # 使用前两部分作为模块标识，如 'ui.panel', 'ui.components' 等
                module = '.'.join(parts[:2])
            elif len(parts) == 1:
                module = parts[0]
            else:
                module = 'other'
            
            modules[module].append(key)
        
        # 按模块缺失数量排序
        sorted_modules = dict(sorted(modules.items(), key=lambda x: len(x[1]), reverse=True))
        return sorted_modules
    
    def generate_report(self):
        """生成翻译覆盖率报告"""
        self.log("\n" + "="*60)
        self.log("翻译合并报告")
        self.log("="*60)
        
        coverage = (self.stats["translated_keys"] / self.stats["total_keys"] * 100) if self.stats["total_keys"] > 0 else 0
        
        self.log(f"统计信息:")
        self.log(f"  - 英文源键数 (en.json): {self.stats['total_keys']:,}")
        self.log(f"  - {self.language_code} 翻译键数: {len(self.flat_translations):,}")
        self.log(f"  - 成功匹配键数: {self.stats['translated_keys']:,}")
        self.log(f"  - 缺失匹配键数: {self.stats['missing_keys']:,}")
        self.log(f"  - 翻译覆盖率: {coverage:.2f}%")
        self.log(f"  - 处理文件数: {self.stats['processed_files']}/{self.stats['total_files']}")
        self.log(f"  - 重复键数: {len(self.stats['duplicate_keys'])}")
        
        if self.stats['duplicate_keys']:
            self.log("\n重复键统计 (最后读取的覆盖之前的):")
            for key, count in list(self.stats['duplicate_keys'].items())[:10]:  # 显示前10个
                self.log(f"  - {key}: {count+1} 次")
            if len(self.stats['duplicate_keys']) > 10:
                self.log(f"  ... 还有 {len(self.stats['duplicate_keys']) - 10} 个重复键")
        
        if self.missing_keys:
            # 按模块分析缺失键
            missing_by_module = self.analyze_missing_by_module(self.missing_keys)
            
            self.log(f"\n缺失翻译按模块分布 (共 {len(self.missing_keys)} 个):")
            total_percent = 0
            for i, (module, keys) in enumerate(list(missing_by_module.items())[:10]):  # 显示前10个模块
                percent = len(keys) / len(self.missing_keys) * 100
                total_percent += percent
                self.log(f"  - {module}: {len(keys):3d} 个 ({percent:.1f}%)")
                # 显示该模块的前几个键作为示例
                if len(keys) > 0 and i < 5:  # 只在前5个模块中显示示例
                    for key in keys[:3]:  # 每个模块显示最多3个示例
                        self.log(f"      * {key}")
            
            if len(missing_by_module) > 10:
                other_count = sum(len(keys) for _, keys in list(missing_by_module.items())[10:])
                other_percent = other_count / len(self.missing_keys) * 100
                self.log(f"  - 其他 {len(missing_by_module)-10} 个模块: {other_count} 个 ({other_percent:.1f}%)")
            
            self.log(f"\n缺失翻译示例 (前20个):")
            for i, key in enumerate(self.missing_keys[:20]):
                self.log(f"  {i+1:3d}. {key}")
            if len(self.missing_keys) > 20:
                self.log(f"  ... 还有 {len(self.missing_keys) - 20} 个缺失翻译")
            
            # 保存完整缺失列表到文件
            missing_file = os.path.join(self.base_dir, "missing_translations.txt")
            with open(missing_file, 'w', encoding='utf-8') as f:
                f.write(f"缺失翻译列表 ({self.language_code}):\n")
                f.write("="*60 + "\n")
                f.write(f"总计: {len(self.missing_keys)} 个缺失翻译\n")
                f.write(f"英文源键数: {self.stats['total_keys']}\n")
                f.write(f"翻译覆盖率: {coverage:.2f}%\n")
                f.write("="*60 + "\n\n")
                
                # 按模块保存
                for module, keys in missing_by_module.items():
                    f.write(f"\n[{module}] - {len(keys)} 个:\n")
                    f.write("-"*40 + "\n")
                    for key in sorted(keys):
                        f.write(f"{key}\n")
            
            self.log(f"完整缺失列表已保存到: {missing_file}")
        
        self.log("\n" + "="*60)
    
    def run(self):
        """执行主流程"""
        self.log(f"开始 {self.language_code} 翻译合并处理")
        self.log(f"工作目录: {self.base_dir}")
        self.log(f"目标语言: {self.language_code}")
        self.log(f"输出文件: {os.path.basename(self.output_file)}")
        
        # 步骤1: 查找所有指定语言的翻译文件
        translation_files = self.find_translation_files()
        if not translation_files:
            self.error(f"未找到任何 {self.language_code}-*.json 文件，退出")
            sys.exit(1)
        
        # 步骤2: 提取并合并扁平化翻译
        self.extract_flat_translations(translation_files)
        
        # 步骤3: 分析 en.json 结构
        en_template = self.analyze_en_structure()
        
        # 步骤4: 重建嵌套结构
        translated_data = self.rebuild_translation_structure(en_template)
        
        # 步骤5: 保存输出文件
        self.save_translation_file(translated_data)
        
        # 步骤6: 结构对比验证
        self.compare_structures()
        
        # 步骤7: 生成报告
        self.generate_report()
        
        self.log("处理完成!")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Home Assistant 多语言翻译合并工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 合并简体中文翻译 (默认)
  python merge_translations.py
  
  # 合并繁体中文翻译
  python merge_translations.py --lang zh-Hant
  
  # 合并法语翻译
  python merge_translations.py --lang fr
  
  # 指定工作目录
  python merge_translations.py --dir /path/to/translations --lang de
  
  # 显示帮助信息
  python merge_translations.py --help

功能说明:
  1. 扫描指定目录中的 translations/ 子目录
  2. 查找指定语言的所有翻译文件 (如 zh-Hans-*.json)
  3. 以 en.json 为模板重建嵌套结构
  4. 生成结构完全相同的语言包文件 (如 zh.json)
  5. 验证结构一致性并生成翻译覆盖率报告
  
输出文件:
  - {lang}.json: 完整的嵌套结构翻译文件 (如 zh.json, fr.json)
  - missing_translations.txt: 缺失翻译列表
  - 控制台显示详细的处理统计信息
"""
    )
    
    parser.add_argument(
        "--dir", "-d",
        type=str,
        help="工作目录路径（包含 en.json 和 translations/ 目录）",
        default=None
    )
    
    parser.add_argument(
        "--lang", "-l",
        type=str,
        help="语言代码 (如 zh-Hans, zh-Hant, fr, de, es 等)，默认: zh-Hans",
        default="zh-Hans"
    )
    
    args = parser.parse_args()
    
    # 确定工作目录
    if args.dir:
        work_dir = os.path.abspath(args.dir)
        if not os.path.exists(work_dir):
            print(f"错误: 指定的目录不存在: {work_dir}", file=sys.stderr)
            sys.exit(1)
    else:
        # 默认使用脚本所在目录
        work_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"工作目录: {work_dir}")
    
    # 检查必要文件
    en_file = os.path.join(work_dir, "en.json")
    translations_dir = os.path.join(work_dir, "translations")
    
    if not os.path.exists(en_file):
        print(f"错误: 未找到 en.json 文件: {en_file}", file=sys.stderr)
        print("请确保工作目录包含 en.json 文件", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(translations_dir):
        print(f"错误: 未找到 translations 目录: {translations_dir}", file=sys.stderr)
        print("请确保工作目录包含 translations/ 子目录", file=sys.stderr)
        sys.exit(1)
    
    # 创建合并器实例
    merger = TranslationMerger(work_dir, args.lang)
    
    try:
        merger.run()
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"未处理的错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()