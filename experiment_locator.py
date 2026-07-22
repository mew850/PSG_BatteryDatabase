#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验数据定位器 - 支持多文件多轴灵活对比（兼容姓名查询）
依赖：pandas, matplotlib, tkinter
"""

import os
import sys
import subprocess
import json
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# -------------------- 配置 --------------------
MASTER_CSV = "./MasterData.csv"
ARCHIVE_ROOT = "./StructuredArchive"

# -------------------- 工具函数 --------------------
def open_folder(path):
    if not os.path.exists(path):
        messagebox.showerror("错误", f"文件夹不存在：{path}")
        return
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

def get_archive_path(experiment_id):
    date_part = experiment_id.split("_")[0]
    year_month = date_part[:4] + "-" + date_part[4:6]
    return os.path.join(ARCHIVE_ROOT, year_month, experiment_id)

def safe_read_csv(file_path):
    try:
        return pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding='gbk')

def get_columns_from_metadata(archive_path, filename):
    meta_file = os.path.join(archive_path, "experiment_metadata.json")
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            col_info = meta.get("列名信息", {})
            if filename in col_info and col_info[filename] is not None:
                return col_info[filename]
        except:
            pass
    return None

def get_columns_for_file(exp_id, data_filename):
    archive_path = get_archive_path(exp_id)
    columns = get_columns_from_metadata(archive_path, data_filename)
    if columns:
        return columns
    file_path = os.path.join(archive_path, "raw", data_filename)
    if os.path.exists(file_path):
        try:
            df = safe_read_csv(file_path)
            return list(df.columns)
        except:
            pass
    return []

# -------------------- 配置对话框 --------------------
class PlotConfigDialog(tk.Toplevel):
    def __init__(self, parent, records):
        super().__init__(parent)
        self.title("曲线对比配置")
        self.records = records
        self.result = None

        ttk.Label(self, text="请为每个文件选择 X 轴和 Y 轴数据列", font=("Arial", 10, "bold")).pack(pady=10)

        canvas = tk.Canvas(self, width=700, height=300)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y")

        self.config_widgets = []

        for idx, (exp_id, sample_id, test_type, file_path) in enumerate(records):
            frame = ttk.LabelFrame(scroll_frame, text=f"{os.path.basename(file_path)} ({sample_id})")
            frame.pack(fill="x", padx=5, pady=5)

            columns = get_columns_for_file(exp_id, os.path.basename(file_path))

            ttk.Label(frame, text="X 轴列名:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
            x_var = tk.StringVar()
            x_combo = ttk.Combobox(frame, textvariable=x_var, values=columns, state="readonly", width=25)
            x_combo.grid(row=0, column=1, padx=5, pady=2, sticky="w")
            for col in columns:
                col_lower = col.lower()
                if any(kw in col_lower for kw in ['循环号', 'cycle', 'freq', '频率', 'time', '时间']):
                    x_var.set(col)
                    break

            ttk.Label(frame, text="Y 轴列名:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
            y_var = tk.StringVar()
            y_combo = ttk.Combobox(frame, textvariable=y_var, values=columns, state="readonly", width=25)
            y_combo.grid(row=1, column=1, padx=5, pady=2, sticky="w")
            for col in columns:
                col_lower = col.lower()
                if any(kw in col_lower for kw in ['放电比容量', 'discharge', 'capacity', "z'", 'zreal', '实部', '电阻', '电压', '比容量']):
                    y_var.set(col)
                    break

            self.config_widgets.append((file_path, sample_id, exp_id, x_var, y_var))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确认并绘图", command=self.on_confirm).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="取消", command=self.on_cancel).pack(side="left", padx=10)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def on_confirm(self):
        configs = []
        for file_path, sample_id, exp_id, x_var, y_var in self.config_widgets:
            x_col = x_var.get().strip()
            y_col = y_var.get().strip()
            if not x_col or not y_col:
                messagebox.showwarning("配置不完整", f"文件 {os.path.basename(file_path)} 未选择 X 轴或 Y 轴列名")
                return
            label = f"{sample_id} ({os.path.basename(file_path)})"
            configs.append((file_path, x_col, y_col, label))
        self.result = configs
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

# -------------------- 多轴绘图函数 --------------------
def plot_multi_axis_comparison(configs):
    """
    configs: [(file_path, x_col, y_col, label), ...]
    自动分组：相同 (x_col, y_col) 使用同一坐标轴；
    不同 Y 列名自动创建新的 Y 轴（右侧偏移）。
    """
    x_cols = set(c[1] for c in configs)
    if len(x_cols) > 1:
        messagebox.showerror("X轴不一致", "所选文件的 X 轴列名不一致，无法在同一张图中对比。请重新配置。")
        return

    x_col = configs[0][1]

    groups = {}
    for file_path, xc, y_col, label in configs:
        key = (xc, y_col)
        groups.setdefault(key, []).append((file_path, label))

    fig, ax1 = plt.subplots(figsize=(12, 7))
    colors = plt.cm.tab10.colors
    color_idx = 0
    axes = [ax1]
    group_keys = list(groups.keys())

    # 第一组：左轴
    first_key = group_keys[0]
    _, first_ycol = first_key
    ax1.set_xlabel(x_col)
    ax1.set_ylabel(first_ycol, color=colors[color_idx % len(colors)])
    ax1.tick_params(axis='y', labelcolor=colors[color_idx % len(colors)])

    for file_path, label in groups[first_key]:
        try:
            df = safe_read_csv(file_path)
            df[x_col] = pd.to_numeric(df[x_col], errors='coerce')
            df[first_ycol] = pd.to_numeric(df[first_ycol], errors='coerce')
            df = df.dropna(subset=[x_col, first_ycol])
            ax1.plot(df[x_col], df[first_ycol],
                     marker='o', markersize=4,
                     markerfacecolor='white',
                     markeredgewidth=1.0,
                     linestyle='-', linewidth=1.0,
                     color=colors[color_idx % len(colors)],
                     label=label)
            color_idx += 1
        except Exception as e:
            messagebox.showwarning("数据错误", f"绘制 {label} 时出错：{e}")

    # 后续组：新的 Y 轴
    for i, key in enumerate(group_keys[1:], start=1):
        _, y_col = key
        ax_new = ax1.twinx()
        offset = 60 * i
        ax_new.spines['right'].set_position(('outward', offset))
        clr = colors[color_idx % len(colors)]
        ax_new.set_ylabel(y_col, color=clr)
        ax_new.tick_params(axis='y', labelcolor=clr)
        for file_path, label in groups[key]:
            try:
                df = safe_read_csv(file_path)
                df[x_col] = pd.to_numeric(df[x_col], errors='coerce')
                df[y_col] = pd.to_numeric(df[y_col], errors='coerce')
                df = df.dropna(subset=[x_col, y_col])
                ax_new.plot(df[x_col], df[y_col],
                            marker='s', markersize=4,
                            markerfacecolor='white',
                            markeredgewidth=1.0,
                            linestyle='--', linewidth=1.0,
                            color=clr,
                            label=label)
                color_idx += 1
            except Exception as e:
                messagebox.showwarning("数据错误", f"绘制 {label} 时出错：{e}")

    # 合并图例
    lines, labels = [], []
    for ax in axes:
        for line in ax.get_lines():
            lines.append(line)
            labels.append(line.get_label())
    unique = {}
    for l, lab in zip(lines, labels):
        if lab not in unique:
            unique[lab] = l
    ax1.legend(unique.values(), unique.keys(), loc='best')
    ax1.grid(True, linestyle='--', alpha=0.6)
    plt.title("多文件数据对比（多轴自适应）")
    fig.tight_layout()
    plt.show()

# -------------------- 主界面 --------------------
class LocatorApp:
    def __init__(self, root):
        self.root = root
        root.title("实验数据定位器（支持多轴对比）")
        root.geometry("1000x650")

        if not os.path.exists(MASTER_CSV):
            messagebox.showerror("错误", f"未找到汇总文件：{MASTER_CSV}\n请先运行数据收集脚本。")
            root.destroy()
            return
        self.df = pd.read_csv(MASTER_CSV, dtype=str)

        # ---- 查询条件区域 ----
        query_frame = ttk.LabelFrame(root, text="查询条件（支持模糊匹配，留空则忽略）", padding=10)
        query_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(query_frame, text="样品编号：").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.sample_var = tk.StringVar()
        ttk.Entry(query_frame, textvariable=self.sample_var, width=20).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(query_frame, text="测试类型：").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.type_var = tk.StringVar()
        ttk.Entry(query_frame, textvariable=self.type_var, width=20).grid(row=0, column=3, padx=5, pady=5, sticky="w")

        ttk.Label(query_frame, text="开始年月：").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.date_var = tk.StringVar()
        ttk.Entry(query_frame, textvariable=self.date_var, width=20).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(query_frame, text="数据文件名：").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.file_var = tk.StringVar()
        ttk.Entry(query_frame, textvariable=self.file_var, width=20).grid(row=1, column=3, padx=5, pady=5, sticky="w")

        # 新增：提交人姓名查询
        ttk.Label(query_frame, text="提交人姓名：").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.contact_var = tk.StringVar()
        ttk.Entry(query_frame, textvariable=self.contact_var, width=20).grid(row=2, column=1, padx=5, pady=5, sticky="w")

        btn_frame = ttk.Frame(query_frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=10)
        ttk.Button(btn_frame, text="查询", command=self.search).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="清除条件", command=self.clear).pack(side="left", padx=10)

        # ---- 结果表格 ----
        table_frame = ttk.LabelFrame(root, text="查询结果（支持 Ctrl/Shift 多选，双击打开文件夹）", padding=10)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("实验ID", "样品编号", "测试类型", "测试开始日期", "数据文件名", "归档路径")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.column("实验ID", width=200)
        self.tree.column("归档路径", width=260)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.on_double_click)

        # 底部按钮
        bottom_frame = ttk.Frame(root)
        bottom_frame.pack(fill="x", padx=10, pady=5)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(bottom_frame, textvariable=self.status_var).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="对比曲线", command=self.compare_curves).pack(side="right", padx=5)
        ttk.Button(bottom_frame, text="打开选中文件夹", command=self.open_selected).pack(side="right", padx=5)

    def search(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        mask = pd.Series([True] * len(self.df))
        sample = self.sample_var.get().strip()
        test_type = self.type_var.get().strip()
        date_str = self.date_var.get().strip()
        filename = self.file_var.get().strip()
        contact = self.contact_var.get().strip()   # 新增姓名搜索条件

        if sample:
            mask &= self.df["样品编号"].str.contains(sample, na=False, case=False)
        if test_type:
            mask &= self.df["测试类型"].str.contains(test_type, na=False, case=False)
        if date_str:
            mask &= self.df["测试开始日期"].str.startswith(date_str, na=False)
        if filename:
            mask &= self.df["数据文件名"].str.contains(filename, na=False, case=False)
        if contact:   # 模糊匹配提交人姓名
            mask &= self.df["提交人姓名"].str.contains(contact, na=False, case=False)

        results = self.df[mask]
        if results.empty:
            self.status_var.set("未找到匹配的实验")
            return
        for _, row in results.iterrows():
            exp_id = row["实验ID"]
            archive_path = get_archive_path(exp_id)
            self.tree.insert("", "end", values=(
                exp_id, row.get("样品编号", ""), row.get("测试类型", ""),
                row.get("测试开始日期", ""), row.get("数据文件名", ""), archive_path
            ))
        self.status_var.set(f"找到 {len(results)} 条记录")

    def clear(self):
        self.sample_var.set("")
        self.type_var.set("")
        self.date_var.set("")
        self.file_var.set("")
        self.contact_var.set("")   # 清空姓名
        self.search()

    def on_double_click(self, event):
        self.open_selected()

    def open_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一条记录")
            return
        item = self.tree.item(selected[0])
        archive_path = item["values"][-1]
        open_folder(archive_path)

    def compare_curves(self):
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("缺少依赖", "对比功能需要 matplotlib 库。")
            return
        selected_items = self.tree.selection()
        if len(selected_items) < 2:
            messagebox.showwarning("选择不足", "请至少选择两个实验数据文件（Ctrl+点击多选）")
            return

        records = []
        for item_id in selected_items:
            values = self.tree.item(item_id)["values"]
            exp_id = values[0]
            sample_id = values[1]
            test_type = values[2]
            data_filename = values[4]
            archive_path = values[5]
            file_path = os.path.join(archive_path, "raw", data_filename)
            if not os.path.exists(file_path):
                messagebox.showerror("文件缺失", f"找不到数据文件：{file_path}")
                return
            records.append((exp_id, sample_id, test_type, file_path))

        dlg = PlotConfigDialog(self.root, records)
        if dlg.result is None:
            return
        plot_multi_axis_comparison(dlg.result)

if __name__ == "__main__":
    root = tk.Tk()
    app = LocatorApp(root)
    root.mainloop()