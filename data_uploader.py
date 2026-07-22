#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电池数据一键上传工具（GUI版）
- 自动生成实验ID、归档文件夹
- 支持动态测试条件表单
- 多次连续提交，无需关闭窗口
"""

import os
import sys
import shutil
import json
import pandas as pd
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ==================== 配置 ====================
ARCHIVE_ROOT = "./StructuredArchive"     # 归档根目录
MASTER_CSV = "./MasterData.csv"          # 全局汇总表路径

# 必填字段清单（主信息）
MAIN_FIELDS = [
    "样品编号", "电池类型", "标称容量(Ah)", "形态",
    "生产批次", "测试类别", "测试类型", "测试开始日期",
    "测试设备型号"
]

# 测试类别 → 测试类型选项
TEST_TYPE_OPTIONS = {
    "耐久性": ["常温循环", "高温循环", "低温循环"],
    "动力性": ["倍率", "EIS"],
    "安全性": ["DSC", "STA-MS", "ARC", "燃烧弹", "侧向加热", "针刺", "挤压", "热箱", "热蔓延"]
}

# 条件字段定义（根据测试类型，键为测试类型，值为字段列表）
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

# 小组选项
GROUP_OPTIONS = ["不确定", "智能系统-设计", "智能系统-制造", "智能系统-管理", "固态电化学", "电池安全组", "其他"]

# ==================== 核心功能 ====================
def get_next_experiment_id(sample_id, test_type):
    date_str = datetime.now().strftime("%Y%m%d")
    base = f"{date_str}_{sample_id}_{test_type}"
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
        if len(parts) >= 4:
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
        "数据文件列表": "; ".join(copied_files)
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
        "小组": metadata.get("小组", "")
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

# ==================== GUI 界面 ====================
class UploaderApp:
    def __init__(self, root):
        self.root = root
        root.title("电池数据一键上传")
        root.geometry("780x800")
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
        self.file_list_var = tk.StringVar(value="")
        # 设置红色星号样式
        style = ttk.Style()
        style.configure("Red.TLabel", foreground="red")
        self.build_form()

    def build_form(self):
        # 占位符文本
        sample_placeholder = "例：NMC811-C01"

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        row = 0

        # ---- 基本信息区 ----
        ttk.Label(self.scroll_frame, text="■ 基本信息", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        row += 1

        # ---------- 样品编号（必填，带 placeholder） ----------
        self._make_label(row, "样品编号", required=True)
        var = tk.StringVar()
        self.vars["样品编号"] = var
        sample_entry = ttk.Entry(self.scroll_frame, textvariable=var, width=30)
        sample_entry.grid(row=row, column=1, sticky="w", padx=5)
        # 设置 placeholder 效果
        var.set(sample_placeholder)
        sample_entry.config(foreground="grey")
        def on_focus_in(event):
            if var.get() == sample_placeholder:
                var.set("")
                sample_entry.config(foreground="black")
        def on_focus_out(event):
            if var.get() == "":
                var.set(sample_placeholder)
                sample_entry.config(foreground="grey")
        sample_entry.bind("<FocusIn>", on_focus_in)
        sample_entry.bind("<FocusOut>", on_focus_out)
        # 保存占位符文本和输入框引用，供 submit 和重置使用
        self.sample_placeholder = sample_placeholder
        self.sample_entry = sample_entry
        row += 1

        # ---------- 其余信息字段 ----------
        other_fields = [
            ("电池类型", False),
            ("标称容量(Ah)", False),
            ("形态", False),
            ("生产批次", False),
            ("测试开始日期", False)
        ]
        for label, required in other_fields:
            self._make_label(row, label, required)
            var = tk.StringVar()
            self.vars[label] = var
            ttk.Entry(self.scroll_frame, textvariable=var, width=30).grid(row=row, column=1, sticky="w", padx=5)
            if label == "测试开始日期":
                var.set(datetime.now().strftime("%Y-%m-%d"))
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
        self.type_combo.bind("<<ComboboxSelected>>", self.update_condition_fields)
        row += 1

        # 测试设备型号
        self._make_label(row, "测试设备型号", required=False)
        self.device_var = tk.StringVar()
        self.vars["测试设备型号"] = self.device_var
        ttk.Entry(self.scroll_frame, textvariable=self.device_var, width=30).grid(row=row, column=1, sticky="w", padx=5)
        self.device_var.set("新威 CT-4008-5V10mA")
        row += 1

        # 设备软件版本
        self._make_label(row, "设备软件版本", required=False)
        self.software_var = tk.StringVar()
        self.vars["设备软件版本"] = self.software_var
        ttk.Entry(self.scroll_frame, textvariable=self.software_var, width=30).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # 文件内容说明
        self._make_label(row, "文件内容说明", required=False)
        self.desc_var = tk.StringVar()
        self.vars["文件内容说明"] = self.desc_var
        ttk.Entry(self.scroll_frame, textvariable=self.desc_var, width=30).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # 备注
        self._make_label(row, "备注", required=False)
        self.remark_var = tk.StringVar()
        self.vars["备注"] = self.remark_var
        ttk.Entry(self.scroll_frame, textvariable=self.remark_var, width=30).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        # ---- 提交人信息区 ----
        ttk.Label(self.scroll_frame, text="■ 提交人信息（选填）", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        row += 1

        self._make_label(row, "提交人姓名", required=False)
        self.contact_name_var = tk.StringVar()
        self.vars["提交人姓名"] = self.contact_name_var
        ttk.Entry(self.scroll_frame, textvariable=self.contact_name_var, width=30).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        self._make_label(row, "联系电话", required=False)
        self.contact_phone_var = tk.StringVar()
        self.vars["联系电话"] = self.contact_phone_var
        ttk.Entry(self.scroll_frame, textvariable=self.contact_phone_var, width=30).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        self._make_label(row, "邮箱", required=False)
        self.contact_email_var = tk.StringVar()
        self.vars["邮箱"] = self.contact_email_var
        ttk.Entry(self.scroll_frame, textvariable=self.contact_email_var, width=30).grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        self._make_label(row, "小组", required=False)
        self.group_var = tk.StringVar()
        self.vars["小组"] = self.group_var
        group_combo = ttk.Combobox(self.scroll_frame, textvariable=self.group_var, values=GROUP_OPTIONS, state="readonly", width=28)
        group_combo.grid(row=row, column=1, sticky="w", padx=5)
        group_combo.set("不确定")
        row += 1

        # ---- 条件参数区（动态） ----
        ttk.Label(self.scroll_frame, text="■ 测试条件参数", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        row += 1
        self.cond_frame = ttk.Frame(self.scroll_frame)
        self.cond_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=10)
        self.condition_widgets = []
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

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(side="bottom", fill="x")
        
    def _make_label(self, row, text, required=False):
        """创建一个标签，若 required 则在文字后显示红色 * 号"""
        frame = ttk.Frame(self.scroll_frame)
        frame.grid(row=row, column=0, sticky="e", padx=5, pady=2)
        lbl = ttk.Label(frame, text=text + ":")
        lbl.pack(side="left")
        if required:
            star = ttk.Label(frame, text="*", style="Red.TLabel")
            star.pack(side="left")

    def update_test_types(self, event=None):
        category = self.category_var.get()
        if category in TEST_TYPE_OPTIONS:
            self.type_combo["values"] = TEST_TYPE_OPTIONS[category]
            self.type_var.set("")
            self.clear_condition_fields()

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
                "循环温度(℃)": "25",
                "充电截止电压(V)": "4.2",
                "放电截止电压(V)": "2.5",
                "充电倍率(C)": "0.5",
                "放电倍率(C)": "1.0",
                "恒压充电截止电流": "0.05C",
                "循环周数": "500",
                "休息时间(min)": "10",
                "环境箱型号": "爱斯佩克 ESL-04",
                "温度偏差(℃)": "±1",
                "测试项目": "倍率放电",
                "SOC状态(%)": "100",
                "倍率序列(C)": "0.2,0.5,1,2,3",
                "环境温度(℃)": "25",
                "EIS频率范围": "10mHz-100kHz",
                "EIS扰动幅度(mV)": "5",
                "EIS每个频点采样数": "10",
                "样品质量(mg)": "3.0",
                "坩埚类型": "氧化铝",
                "气氛": "N2",
                "气体流量(mL/min)": "50",
                "升温程序": "30-350@5",
                "测试方法": "针刺",
                "样品荷电状态(%)": "100",
                "针刺速度(mm/s)": "20",
                "温度采集点位数量": "3",
                "温度传感器类型": "K型热电偶",
                "数采设备型号": "横河 GM10"
            }
            for field, var in self.condition_widgets:
                if field in defaults:
                    var.set(defaults[field])

    def clear_condition_fields(self):
        for widget in self.cond_frame.winfo_children():
            widget.destroy()
        self.condition_widgets = []

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
        # 0. 检查 ID 核心字段（将占位符视为空）
        sample_val = self.vars["样品编号"].get().strip()
        category_val = self.vars["测试类别"].get().strip()
        type_val = self.vars["测试类型"].get().strip()

        missing_id = []
        if sample_val == "" or sample_val == self.sample_placeholder:
            missing_id.append("样品编号")
        if not category_val:
            missing_id.append("测试类别")
        if not type_val:
            missing_id.append("测试类型")

        if missing_id:
            messagebox.showerror("缺少ID信息", f"以下带 * 的字段是生成实验ID所必需的，请填写完整：\n{', '.join(missing_id)}")
            return

        # 1. 校验所有必填项
        required = ["样品编号", "电池类型", "标称容量(Ah)", "形态", "测试类别", "测试类型", "测试开始日期", "测试设备型号"]
        for field in required:
            val = self.vars[field].get().strip()
            if field == "样品编号" and val == self.sample_placeholder:
                val = ""  # 占位符视为空
            if not val:
                messagebox.showerror("错误", f"“{field}”为必填项，请填写完整。")
                return

        # 2. 获取文件列表
        file_paths = list(self.file_listbox.get(0, tk.END))
        if not file_paths:
            messagebox.showerror("错误", "请至少选择一个原始数据文件。")
            return

        # 2.5 检查空文件
        empty_files = []
        for fp in file_paths:
            if not os.path.isfile(fp):
                messagebox.showerror("错误", f"文件不存在：{fp}")
                return
            if os.path.getsize(fp) == 0:
                empty_files.append(os.path.basename(fp))
        if empty_files:
            messagebox.showerror("空文件错误", f"以下文件为空（0 字节），请检查后重新选择：\n{', '.join(empty_files)}")
            return

        # 3. 构建元数据
        metadata = {}
        for field in MAIN_FIELDS:
            val = self.vars[field].get().strip()
            if field == "样品编号" and val == self.sample_placeholder:
                val = ""  # 虽然已经校验过，但安全起见
            metadata[field] = val
        metadata["设备软件版本"] = self.software_var.get().strip()
        metadata["文件内容说明"] = self.desc_var.get().strip()
        metadata["备注"] = self.remark_var.get().strip()
        metadata["提交人姓名"] = self.vars["提交人姓名"].get().strip()
        metadata["联系电话"] = self.vars["联系电话"].get().strip()
        metadata["邮箱"] = self.vars["邮箱"].get().strip()
        metadata["小组"] = self.vars["小组"].get().strip()

        conditions = {}
        for field, var in self.condition_widgets:
            val = var.get().strip()
            if val:
                conditions[field] = val
        metadata["conditions"] = conditions

        # 4. 生成实验ID（样品编号此时一定有效）
        sample = metadata["样品编号"]
        test_type = metadata["测试类型"]
        experiment_id = get_next_experiment_id(sample, test_type)

        # 5. 归档
        try:
            dest_dir, copied_fnames = archive_files(experiment_id, file_paths, metadata)
        except Exception as e:
            messagebox.showerror("归档失败", f"复制文件时出错：{e}")
            return

        # 6. 更新Master
        try:
            update_master(experiment_id, metadata, copied_fnames)
        except Exception as e:
            messagebox.showerror("汇总失败", f"更新MasterData.csv时出错：{e}")
            return

        # 7. 成功提示
        self.status_var.set(f"上次提交成功：{experiment_id}")
        messagebox.showinfo("提交成功", f"实验 {experiment_id} 已归档。\n共 {len(copied_fnames)} 个文件。")

        # 8. 重置表单
        for key in ["样品编号", "电池类型", "标称容量(Ah)", "形态", "生产批次", "测试开始日期", "文件内容说明", "备注"]:
            if key in self.vars:
                self.vars[key].set("")
        # 恢复样品编号的 placeholder
        self.vars["样品编号"].set(self.sample_placeholder)
        self.sample_entry.config(foreground="grey")
        self.vars["测试开始日期"].set(datetime.now().strftime("%Y-%m-%d"))
        self.category_var.set("")
        self.type_var.set("")
        self.clear_files()
        self.clear_condition_fields()

if __name__ == "__main__":
    root = tk.Tk()
    app = UploaderApp(root)
    root.mainloop()