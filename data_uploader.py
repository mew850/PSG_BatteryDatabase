#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电池数据一键上传工具（GUI版）
- 所有文本输入框均带有占位符示例
- 自动生成实验ID（包含提交人姓名）
- 支持动态测试条件表单、自定义类型与参数
"""

import os, sys, shutil, json, csv, re, pandas as pd
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ==================== 配置 ====================
ARCHIVE_ROOT = "./StructuredArchive"
MASTER_CSV = "./MasterData.csv"

MAIN_FIELDS = [
    "样品编号", "电池类型", "标称容量(Ah)", "形态",
    "生产批次", "测试类别", "测试类型", "测试开始日期",
    "测试设备型号"
]

TEST_TYPE_OPTIONS = {
    "耐久性": ["常温循环", "高温循环", "低温循环"],
    "动力性": ["倍率", "EIS"],
    "安全性": ["DSC", "STA-MS", "ARC", "燃烧弹", "侧向加热", "针刺", "挤压", "热箱", "热蔓延"]
}

CONDITION_FIELDS = {
    "常温循环": ["循环温度(℃)", "充电截止电压(V)", "放电截止电压(V)", "充电倍率(C)", "放电倍率(C)", "恒压充电截止电流", "循环周数", "充放电顺序", "休息时间(min)", "环境箱型号", "温度偏差(℃)"],
    "高温循环": ["循环温度(℃)", "充电截止电压(V)", "放电截止电压(V)", "充电倍率(C)", "放电倍率(C)", "恒压充电截止电流", "循环周数", "充放电顺序", "休息时间(min)", "环境箱型号", "温度偏差(℃)"],
    "低温循环": ["循环温度(℃)", "充电截止电压(V)", "放电截止电压(V)", "充电倍率(C)", "放电倍率(C)", "恒压充电截止电流", "循环周数", "充放电顺序", "休息时间(min)", "环境箱型号", "温度偏差(℃)"],
    "倍率": ["测试项目", "SOC状态(%)", "倍率序列(C)", "每个倍率持续时间(s)", "环境温度(℃)"],
    "EIS": ["测试项目", "SOC状态(%)", "EIS频率范围", "EIS扰动幅度(mV)", "EIS每个频点采样数", "环境温度(℃)"],
    "DSC": ["样品质量(mg)", "坩埚类型", "气氛", "气体流量(mL/min)", "升温程序", "联用设备", "质谱跟踪质量数"],
    "STA-MS": ["样品质量(mg)", "坩埚类型", "气氛", "气体流量(mL/min)", "升温程序", "联用设备", "质谱跟踪质量数"],
    "ARC": ["测试方法", "样品荷电状态(%)", "ARC起始温度(℃)", "ARC步阶温度(℃)", "温度采集点位数量", "温度传感器类型", "数采设备型号"],
    "燃烧弹": ["测试方法", "样品荷电状态(%)", "加热功率(W)/加热温度(℃)", "温度采集点位数量", "温度传感器类型", "数采设备型号"],
    "侧向加热": ["测试方法", "样品荷电状态(%)", "加热功率(W)/加热温度(℃)", "温度采集点位数量", "温度传感器类型", "数采设备型号"],
    "针刺": ["测试方法", "样品荷电状态(%)", "针刺速度(mm/s)", "温度采集点位数量", "温度传感器类型", "数采设备型号"],
    "挤压": ["测试方法", "样品荷电状态(%)", "挤压速度(mm/min)", "挤压终止条件", "温度采集点位数量", "温度传感器类型", "数采设备型号"],
    "热箱": ["测试方法", "样品荷电状态(%)", "热箱目标温度(℃)", "升温速率(℃/min)", "温度采集点位数量", "温度传感器类型", "数采设备型号"],
    "热蔓延": ["测试方法", "样品荷电状态(%)", "加热功率(W)/加热温度(℃)", "温度采集点位数量", "温度传感器类型", "数采设备型号"]
}

GROUP_OPTIONS = ["不确定", "智能系统-设计", "智能系统-制造", "智能系统-管理", "固态电化学", "电池安全组", "其他"]

# 占位符字典
PLACEHOLDERS = {
    "样品编号": "例：NMC811-C01",
    "电池类型": "例：NMC811/石墨",
    "标称容量(Ah)": "例：2.5",
    "形态": "例：软包",
    "生产批次": "例：Batch202603",
    "测试开始日期": datetime.now().strftime("%Y-%m-%d"),  # 有默认值，不显示占位符
    "测试设备型号": "例：新威 CT-4008-5V10mA",
    "设备软件版本": "例：BTS 8.0",
    "文件内容说明": "例：循环充放电数据",
    "备注": "例：测试中温度波动",
    "提交人姓名": "例：张三",
    "联系电话": "例：13800138000",
    "邮箱": "例：zhangsan@lab.edu",
    "出自文章": "例：ACS Energy Lett. 2024",
    "出自项目": "例：国家重点研发计划 2023YFB2504600",
}

# ==================== 核心功能 ====================
def get_next_experiment_id(sample_id, test_type, contact_name):
    date_str = datetime.now().strftime("%Y%m%d")
    clean_name = contact_name.strip().replace(" ", "_")
    clean_name = "".join(c for c in clean_name if c.isalnum() or c in "_-")
    if not clean_name:
        clean_name = "Unknown"
    base = f"{date_str}_{sample_id}_{test_type}_{clean_name}"
    existing_dirs = []
    for year_month in os.listdir(ARCHIVE_ROOT):
        month_path = os.path.join(ARCHIVE_ROOT, year_month)
        if os.path.isdir(month_path):
            for exp_dir in os.listdir(month_path):
                if exp_dir.startswith(base):
                    existing_dirs.append(exp_dir)
    max_seq = 0
    for d in existing_dirs:
        parts = d.split("_")
        if len(parts) >= 5:
            try:
                seq = int(parts[-1])
                max_seq = max(max_seq, seq)
            except:
                pass
    seq = max_seq + 1
    return f"{base}_{seq:02d}"

def archive_files(experiment_id, data_files, metadata_dict):
    date_part = experiment_id.split("_")[0]
    year_month = date_part[:4] + "-" + date_part[4:6]
    dest_dir = os.path.join(ARCHIVE_ROOT, year_month, experiment_id)
    raw_dir = os.path.join(dest_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    copied_files = []
    for src_path in data_files:
        fname = os.path.basename(src_path)
        dest_path = os.path.join(raw_dir, fname)
        shutil.copy2(src_path, dest_path)
        copied_files.append(fname)

    meta_json_path = os.path.join(dest_dir, "experiment_metadata.json")
    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata_dict, f, ensure_ascii=False, indent=2)

    meta_csv_path = os.path.join(dest_dir, "experiment_info.csv")
    record = {
        "实验ID": experiment_id,
        "样品编号": metadata_dict.get("样品编号", ""),
        "测试类别": metadata_dict.get("测试类别", ""),
        "测试类型": metadata_dict.get("测试类型", ""),
        "测试开始日期": metadata_dict.get("测试开始日期", ""),
        "数据文件列表": "; ".join(copied_files),
        "提交人姓名": metadata_dict.get("提交人姓名", ""),
        "出自文章": metadata_dict.get("出自文章", ""),
        "出自项目": metadata_dict.get("出自项目", "")
    }
    conditions = metadata_dict.get("conditions", {})
    record.update(conditions)
    pd.DataFrame([record]).to_csv(meta_csv_path, index=False, encoding="utf-8-sig")
    return dest_dir, copied_files

def update_master(experiment_id, metadata, data_files):
    base = {
        "实验ID": experiment_id,
        "样品编号": metadata.get("样品编号", ""),
        "电池类型": metadata.get("电池类型", ""),
        "标称容量(Ah)": metadata.get("标称容量(Ah)", ""),
        "形态": metadata.get("形态", ""),
        "生产批次": metadata.get("生产批次", ""),
        "测试类别": metadata.get("测试类别", ""),
        "测试类型": metadata.get("测试类型", ""),
        "测试开始日期": metadata.get("测试开始日期", ""),
        "测试设备型号": metadata.get("测试设备型号", ""),
        "设备软件版本": metadata.get("设备软件版本", ""),
        "文件内容说明": metadata.get("文件内容说明", ""),
        "备注": metadata.get("备注", ""),
        "提交人姓名": metadata.get("提交人姓名", ""),
        "联系电话": metadata.get("联系电话", ""),
        "邮箱": metadata.get("邮箱", ""),
        "小组": metadata.get("小组", ""),
        "出自文章": metadata.get("出自文章", ""),
        "出自项目": metadata.get("出自项目", "")
    }
    cond = metadata.get("conditions", {})
    rows = []
    for fname in data_files:
        row = base.copy()
        row["数据文件名"] = fname
        row["文件格式"] = os.path.splitext(fname)[1].replace(".", "")
        row["是否有导出文件"] = "否"
        row["导出文件名"] = ""
        row.update(cond)
        rows.append(row)

    if os.path.exists(MASTER_CSV):
        df_old = pd.read_csv(MASTER_CSV, dtype=str)
        df_new = pd.DataFrame(rows)
        for col in df_old.columns:
            if col not in df_new.columns:
                df_new[col] = ""
        df_combined = pd.concat([df_old, df_new], ignore_index=True, sort=False)
    else:
        df_combined = pd.DataFrame(rows)
    df_combined.to_csv(MASTER_CSV, index=False, encoding="utf-8-sig")

# ==================== CSV 列名预览对话框（不变）====================
class ColumnDialog(tk.Toplevel):
    def __init__(self, parent, filepath):
        super().__init__(parent)
        self.title("CSV 列名确认")
        self.filepath = filepath
        self.result = None
        try:
            df_preview = pd.read_csv(filepath, nrows=5, header=None, encoding='utf-8')
        except UnicodeDecodeError:
            df_preview = pd.read_csv(filepath, nrows=5, header=None, encoding='gbk')
        first_row = df_preview.iloc[0].tolist()
        is_numeric = True
        for val in first_row:
            try:
                float(str(val).strip())
            except:
                is_numeric = False
                break
        if is_numeric:
            self.has_headers = False
            self.detected_columns = [f"列{i+1}" for i in range(len(first_row))]
            self.data_rows = df_preview.values.tolist()
        else:
            self.has_headers = True
            self.detected_columns = [str(x).strip() for x in first_row]
            self.data_rows = df_preview.iloc[1:].values.tolist() if len(df_preview) > 1 else []
        ttk.Label(self, text=f"文件：{os.path.basename(filepath)}", font=("Arial", 10, "bold")).pack(padx=10, pady=5)
        preview_frame = ttk.LabelFrame(self, text="数据预览（前5行）", padding=5)
        preview_frame.pack(fill="both", expand=True, padx=10, pady=5)
        cols = ["#0"] + [f"col{i}" for i in range(len(self.detected_columns))]
        self.tree = ttk.Treeview(preview_frame, columns=cols[1:], show="headings", height=6)
        for i, col in enumerate(cols[1:]):
            self.tree.heading(col, text=self.detected_columns[i])
            self.tree.column(col, width=100)
        for row_data in self.data_rows[:5]:
            values = [str(v) for v in row_data]
            self.tree.insert("", "end", values=values)
        self.tree.pack(fill="both", expand=True)
        edit_frame = ttk.Frame(self)
        edit_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(edit_frame, text="列名（逗号分隔）：").pack(side="left")
        col_str = ", ".join(self.detected_columns)
        self.entry_var = tk.StringVar(value=col_str)
        ttk.Entry(edit_frame, textvariable=self.entry_var, width=60).pack(side="left", padx=5)
        if not self.has_headers:
            ttk.Label(self, text="⚠ 未检测到列名，请手动输入（或选择忽略）", foreground="red").pack(pady=2)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确认并保存列名", command=self.on_confirm).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="忽略（不记录列名）", command=self.on_ignore).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="取消", command=self.on_cancel).pack(side="left", padx=5)
        self.transient(parent)
        self.grab_set()
        self.wait_window()
    def on_confirm(self):
        col_str = self.entry_var.get().strip()
        if col_str:
            cols = [c.strip() for c in col_str.split(",") if c.strip()]
            self.result = cols
        else:
            self.result = False
        self.destroy()
    def on_ignore(self):
        self.result = False
        self.destroy()
    def on_cancel(self):
        self.result = None
        self.destroy()

# ==================== GUI 界面 ====================
class UploaderApp:
    def __init__(self, root):
        self.root = root
        root.title("电池数据一键上传")
        root.geometry("800x950")
        root.resizable(True, True)

        canvas = tk.Canvas(root, borderwidth=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)
        self.scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.vars = {}
        self.placeholder_map = {}  # 存储 entry -> placeholder
        self.file_list_var = tk.StringVar(value="")
        self.custom_condition_rows = []
        self.custom_type_entry = None
        style = ttk.Style()
        style.configure("Red.TLabel", foreground="red")
        self.build_form()

    def _create_placeholder_entry(self, parent, field_name, width=30, is_date=False):
        """创建一个带占位符的输入框，返回 (var, entry)"""
        var = tk.StringVar()
        entry = tk.Entry(parent, textvariable=var, width=width, fg="grey")
        placeholder = PLACEHOLDERS.get(field_name, "")
        if is_date:
            # 日期字段有默认值，不设置占位符，直接显示当前日期
            var.set(datetime.now().strftime("%Y-%m-%d"))
            entry.config(fg="black")
            self.vars[field_name] = var
            return var, entry
        if placeholder:
            var.set(placeholder)
            entry.bind("<FocusIn>", lambda e, v=var, p=placeholder, ent=entry: self._on_focus_in(v, p, ent))
            entry.bind("<FocusOut>", lambda e, v=var, p=placeholder, ent=entry: self._on_focus_out(v, p, ent))
            var.trace_add("write", lambda *args, v=var, p=placeholder, ent=entry: self._update_color(v, p, ent))
        self.vars[field_name] = var
        return var, entry

    def _on_focus_in(self, var, placeholder, entry):
        if var.get() == placeholder:
            var.set("")
            entry.config(fg="black")

    def _on_focus_out(self, var, placeholder, entry):
        if var.get() == "":
            var.set(placeholder)
            entry.config(fg="grey")

    def _update_color(self, var, placeholder, entry):
        if var.get() == placeholder:
            entry.config(fg="grey")
        else:
            entry.config(fg="black")

    def _get_clean_value(self, field_name):
        """获取字段值，如果等于占位符则返回空字符串"""
        val = self.vars[field_name].get().strip()
        if field_name in PLACEHOLDERS and val == PLACEHOLDERS[field_name]:
            return ""
        return val

    def build_form(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        row = 0

        ttk.Label(self.scroll_frame, text="■ 基本信息", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        row += 1

        # 样品编号 *（必填，特殊处理 width=30）
        self._make_label(row, "样品编号", required=True)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "样品编号", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        self.sample_entry = entry
        row += 1

        # 其他文本字段
        other_fields = [
            ("电池类型", False),
            ("标称容量(Ah)", False),
            ("形态", False),
            ("生产批次", False),
            ("测试开始日期", True)  # 有默认当前日期，不占位符
        ]
        for label, is_date in other_fields:
            self._make_label(row, label, required=False)
            var, entry = self._create_placeholder_entry(self.scroll_frame, label, width=30, is_date=is_date)
            entry.grid(row=row, column=1, sticky="w", padx=5)
            row += 1

        # 测试类别 *
        self._make_label(row, "测试类别", required=True)
        self.category_var = tk.StringVar()
        self.vars["测试类别"] = self.category_var
        category_combo = ttk.Combobox(self.scroll_frame, textvariable=self.category_var, values=list(TEST_TYPE_OPTIONS.keys()), state="readonly", width=28)
        category_combo.grid(row=row, column=1, sticky="w", padx=5)
        category_combo.bind("<<ComboboxSelected>>", self.update_test_types)
        row += 1

        # 测试类型 *
        self._make_label(row, "测试类型", required=True)
        self.type_var = tk.StringVar()
        self.vars["测试类型"] = self.type_var
        self.type_combo = ttk.Combobox(self.scroll_frame, textvariable=self.type_var, state="readonly", width=28)
        self.type_combo.grid(row=row, column=1, sticky="w", padx=5)
        self.type_combo.bind("<<ComboboxSelected>>", self.on_type_selected)
        row += 1

        # 自定义测试类型输入框（默认隐藏）
        self.custom_type_var = tk.StringVar()
        self.custom_type_entry = ttk.Entry(self.scroll_frame, textvariable=self.custom_type_var, width=28)
        self.custom_type_entry.grid(row=row, column=1, sticky="w", padx=5)
        self.custom_type_entry.grid_remove()
        row += 1

        # 测试设备型号
        self._make_label(row, "测试设备型号", required=False)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "测试设备型号", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        # 设备型号有默认值，不使用占位符，直接设置
        var.set("新威 CT-4008-5V10mA")
        entry.config(fg="black")
        row += 1

        # 设备软件版本
        self._make_label(row, "设备软件版本", required=False)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "设备软件版本", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # 文件内容说明
        self._make_label(row, "文件内容说明", required=False)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "文件内容说明", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # 备注
        self._make_label(row, "备注", required=False)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "备注", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # ---- 提交人信息区 ----
        ttk.Label(self.scroll_frame, text="■ 提交人信息", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        row += 1

        # 提交人姓名 *（必填）
        self._make_label(row, "提交人姓名", required=True)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "提交人姓名", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # 联系电话
        self._make_label(row, "联系电话", required=False)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "联系电话", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # 邮箱
        self._make_label(row, "邮箱", required=False)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "邮箱", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # 小组（下拉）
        self._make_label(row, "小组", required=False)
        self.group_var = tk.StringVar()
        self.vars["小组"] = self.group_var
        group_combo = ttk.Combobox(self.scroll_frame, textvariable=self.group_var, values=GROUP_OPTIONS, state="readonly", width=28)
        group_combo.grid(row=row, column=1, sticky="w", padx=5)
        group_combo.set("不确定")
        row += 1

        # 出自文章
        self._make_label(row, "出自文章", required=False)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "出自文章", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # 出自项目
        self._make_label(row, "出自项目", required=False)
        var, entry = self._create_placeholder_entry(self.scroll_frame, "出自项目", width=30)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # ---- 条件参数区 ----
        ttk.Label(self.scroll_frame, text="■ 测试条件参数", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        row += 1
        self.cond_frame = ttk.Frame(self.scroll_frame)
        self.cond_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=10)
        self.condition_widgets = []
        self.custom_condition_rows = []
        row += 1

        self.add_cond_btn = ttk.Button(self.scroll_frame, text="+ 添加参数", command=self.add_custom_condition)
        self.add_cond_btn.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        # ---- 文件选择区 ----
        ttk.Label(self.scroll_frame, text="■ 原始数据文件（支持多选）", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        row += 1
        self.file_listbox = tk.Listbox(self.scroll_frame, width=80, height=5)
        self.file_listbox.grid(row=row, column=0, columnspan=2, padx=10, pady=5)
        row += 1
        btn_frame = ttk.Frame(self.scroll_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=5)
        ttk.Button(btn_frame, text="添加文件", command=self.add_files).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_files).pack(side="left", padx=5)
        row += 1

        # ---- 提交按钮 ----
        submit_btn = ttk.Button(self.scroll_frame, text="提交当前实验", command=self.submit)
        submit_btn.grid(row=row, column=0, columnspan=2, pady=15)
        row += 1

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(side="bottom", fill="x")

    def _make_label(self, row, text, required=False):
        frame = ttk.Frame(self.scroll_frame)
        frame.grid(row=row, column=0, sticky="e", padx=5, pady=2)
        lbl = ttk.Label(frame, text=text + ":")
        lbl.pack(side="left")
        if required:
            star = ttk.Label(frame, text="*", style="Red.TLabel")
            star.pack(side="left")

    def update_test_types(self, event=None):
        category = self.category_var.get()
        types = list(TEST_TYPE_OPTIONS.get(category, [])) + ["自定义"]
        self.type_combo["values"] = types
        self.type_var.set("")
        self.clear_condition_fields()
        self.hide_custom_type_entry()

    def on_type_selected(self, event=None):
        sel = self.type_var.get()
        if sel == "自定义":
            self.custom_type_entry.grid()
            self.custom_type_var.set("")
            self.custom_type_entry.focus_set()
            self.update_condition_fields(None)
        else:
            self.hide_custom_type_entry()
            self.update_condition_fields(None)

    def hide_custom_type_entry(self):
        if self.custom_type_entry:
            self.custom_type_entry.grid_remove()

    def update_condition_fields(self, event=None):
        self.clear_condition_fields()
        test_type = self.type_var.get()
        if test_type in CONDITION_FIELDS:
            fields = CONDITION_FIELDS[test_type]
            for i, field in enumerate(fields):
                lbl = ttk.Label(self.cond_frame, text=field+":")
                lbl.grid(row=i, column=0, sticky="e", padx=5, pady=2)
                var = tk.StringVar()
                entry = ttk.Entry(self.cond_frame, textvariable=var, width=25)
                entry.grid(row=i, column=1, sticky="w", padx=5)
                self.condition_widgets.append((field, var))
            defaults = {
                "循环温度(℃)": "25", "充电截止电压(V)": "4.2", "放电截止电压(V)": "2.5",
                "充电倍率(C)": "0.5", "放电倍率(C)": "1.0", "恒压充电截止电流": "0.05C",
                "循环周数": "500", "休息时间(min)": "10", "环境箱型号": "爱斯佩克 ESL-04",
                "温度偏差(℃)": "±1", "测试项目": "倍率放电", "SOC状态(%)": "100",
                "倍率序列(C)": "0.2,0.5,1,2,3", "环境温度(℃)": "25",
                "EIS频率范围": "10mHz-100kHz", "EIS扰动幅度(mV)": "5", "EIS每个频点采样数": "10",
                "样品质量(mg)": "3.0", "坩埚类型": "氧化铝", "气氛": "N2",
                "气体流量(mL/min)": "50", "升温程序": "30-350@5",
                "测试方法": "针刺", "样品荷电状态(%)": "100", "针刺速度(mm/s)": "20",
                "温度采集点位数量": "3", "温度传感器类型": "K型热电偶",
                "数采设备型号": "横河 GM10"
            }
            for field, var in self.condition_widgets:
                if field in defaults:
                    var.set(defaults[field])

    def clear_condition_fields(self):
        for widget in self.cond_frame.winfo_children():
            widget.destroy()
        self.condition_widgets = []
        self.custom_condition_rows = []

    def add_custom_condition(self):
        row_idx = len(self.custom_condition_rows)
        frame = ttk.Frame(self.cond_frame)
        frame.grid(row=row_idx+100, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        ttk.Label(frame, text="参数名:").pack(side="left")
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=15).pack(side="left", padx=5)
        ttk.Label(frame, text="参数值:").pack(side="left")
        value_var = tk.StringVar()
        ttk.Entry(frame, textvariable=value_var, width=15).pack(side="left", padx=5)
        del_btn = ttk.Button(frame, text="删除", command=lambda f=frame: self.remove_custom_condition(f))
        del_btn.pack(side="left", padx=5)
        self.custom_condition_rows.append((name_var, value_var, frame))

    def remove_custom_condition(self, frame):
        for i, (name_var, value_var, frm) in enumerate(self.custom_condition_rows):
            if frm == frame:
                frame.destroy()
                del self.custom_condition_rows[i]
                break

    def add_files(self):
        files = filedialog.askopenfilenames(title="选择原始数据文件", filetypes=[("All files", "*.*")])
        if files:
            current = list(self.file_listbox.get(0, tk.END))
            for f in files:
                if f not in current:
                    self.file_listbox.insert(tk.END, f)

    def clear_files(self):
        self.file_listbox.delete(0, tk.END)

    def submit(self):
        # 0. 检查ID核心字段
        sample_val = self._get_clean_value("样品编号")
        category_val = self.vars["测试类别"].get().strip()
        type_val = self.type_var.get().strip()
        contact_val = self._get_clean_value("提交人姓名")

        if type_val == "自定义":
            type_val = self.custom_type_var.get().strip()

        missing_id = []
        if not sample_val:
            missing_id.append("样品编号")
        if not category_val:
            missing_id.append("测试类别")
        if not type_val:
            missing_id.append("测试类型")
        if not contact_val:
            missing_id.append("提交人姓名")
        if missing_id:
            messagebox.showerror("缺少ID信息", f"以下带 * 的字段是生成实验ID所必需的，请填写完整：\n{', '.join(missing_id)}")
            return

        # 1. 校验必填项
        required = ["样品编号", "电池类型", "标称容量(Ah)", "形态", "测试类别", "测试开始日期", "测试设备型号", "提交人姓名"]
        for field in required:
            val = self._get_clean_value(field) if field in PLACEHOLDERS else self.vars[field].get().strip()
            if field == "测试开始日期":   # 日期一定有值
                val = self.vars["测试开始日期"].get().strip()
            if not val:
                messagebox.showerror("错误", f"“{field}”为必填项，请填写完整。")
                return

        file_paths = list(self.file_listbox.get(0, tk.END))
        if not file_paths:
            messagebox.showerror("错误", "请至少选择一个原始数据文件。")
            return
        for fp in file_paths:
            if not os.path.isfile(fp):
                messagebox.showerror("错误", f"文件不存在：{fp}")
                return
            if os.path.getsize(fp) == 0:
                messagebox.showerror("错误", f"文件为空：{os.path.basename(fp)}")
                return

        # CSV 列名处理
        column_info = {}
        for fp in file_paths:
            fname = os.path.basename(fp)
            if fname.lower().endswith('.csv'):
                dlg = ColumnDialog(self.root, fp)
                if dlg.result is None:
                    return
                column_info[fname] = dlg.result
            else:
                column_info[fname] = None

        metadata = {}
        for field in MAIN_FIELDS:
            val = self._get_clean_value(field) if field in PLACEHOLDERS else self.vars[field].get().strip()
            if field == "测试开始日期":
                val = self.vars["测试开始日期"].get().strip()
            metadata[field] = val
        metadata["测试类型"] = type_val
        metadata["设备软件版本"] = self._get_clean_value("设备软件版本")
        metadata["文件内容说明"] = self._get_clean_value("文件内容说明")
        metadata["备注"] = self._get_clean_value("备注")
        metadata["提交人姓名"] = contact_val
        metadata["联系电话"] = self._get_clean_value("联系电话")
        metadata["邮箱"] = self._get_clean_value("邮箱")
        metadata["小组"] = self.vars["小组"].get().strip()
        metadata["出自文章"] = self._get_clean_value("出自文章")
        metadata["出自项目"] = self._get_clean_value("出自项目")
        metadata["列名信息"] = column_info

        conditions = {}
        for field, var in self.condition_widgets:
            val = var.get().strip()
            if val:
                conditions[field] = val
        for name_var, value_var, _ in self.custom_condition_rows:
            name = name_var.get().strip()
            val = value_var.get().strip()
            if name and val:
                conditions[name] = val
        metadata["conditions"] = conditions

        sample = metadata["样品编号"]
        test_type = type_val
        contact = contact_val
        experiment_id = get_next_experiment_id(sample, test_type, contact)

        try:
            dest_dir, copied_fnames = archive_files(experiment_id, file_paths, metadata)
        except Exception as e:
            messagebox.showerror("归档失败", f"复制文件时出错：{e}")
            return

        try:
            update_master(experiment_id, metadata, copied_fnames)
        except Exception as e:
            messagebox.showerror("汇总失败", f"更新MasterData.csv时出错：{e}")
            return

        self.status_var.set(f"上次提交成功：{experiment_id}")
        messagebox.showinfo("提交成功", f"实验 {experiment_id} 已归档。\n共 {len(copied_fnames)} 个文件。")

        # 重置表单（保留联系人信息）
        for key in ["样品编号", "电池类型", "标称容量(Ah)", "形态", "生产批次", "文件内容说明", "备注"]:
            if key in self.vars:
                self.vars[key].set(PLACEHOLDERS.get(key, ""))
        self.vars["测试开始日期"].set(datetime.now().strftime("%Y-%m-%d"))
        self.vars["测试设备型号"].set("新威 CT-4008-5V10mA")
        self.vars["设备软件版本"].set(PLACEHOLDERS["设备软件版本"])
        self.category_var.set("")
        self.type_var.set("")
        self.custom_type_var.set("")
        self.hide_custom_type_entry()
        self.clear_files()
        self.clear_condition_fields()
        # 提交人信息保留，不清空

if __name__ == "__main__":
    root = tk.Tk()
    app = UploaderApp(root)
    root.mainloop()