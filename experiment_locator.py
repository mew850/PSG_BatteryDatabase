#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验数据定位器 - 支持多选对比与曲线堆叠
依赖：pandas, matplotlib, tkinter
"""

import os
import sys
import subprocess
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei"] # 设置字体
plt.rcParams["axes.unicode_minus"] = False # 正常显示负号
# -------------------- 检查 matplotlib 是否可用 --------------------
try:
    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# -------------------- 配置 --------------------
MASTER_CSV = "./MasterData.csv"       # 汇总表路径
ARCHIVE_ROOT = "./StructuredArchive"  # 归档根目录

# -------------------- 工具函数 --------------------
def open_folder(path):
    """跨平台打开文件夹"""
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
    """根据实验ID推算归档路径"""
    date_part = experiment_id.split("_")[0]
    year_month = date_part[:4] + "-" + date_part[4:6]
    return os.path.join(ARCHIVE_ROOT, year_month, experiment_id)

def safe_read_csv(file_path):
    """安全读取CSV，尝试不同编码"""
    try:
        return pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding='gbk')

def plot_cycle_comparison(records):
    """绘制循环数据对比图（放电比容量 vs 循环号）—— 期刊风格空心散点"""
    plt.figure(figsize=(8, 6))
    for exp_id, sample_id, file_path in records:
        try:
            df = safe_read_csv(file_path)
            # 自动识别循环号列（第一列）和放电比容量列
            x_col = df.columns[0]
            y_col = None
            for col in df.columns:
                if '放电比容量' in col or 'discharge' in col.lower() or 'capacity' in col.lower():
                    y_col = col
                    break
            if y_col is None:
                y_col = df.columns[1] if len(df.columns) > 1 else None
            if y_col is None:
                raise ValueError("未找到放电比容量列")
            # 转换为数值并删除无效行
            df[x_col] = pd.to_numeric(df[x_col], errors='coerce')
            df[y_col] = pd.to_numeric(df[y_col], errors='coerce')
            df = df.dropna(subset=[x_col, y_col])
            label = f"{sample_id} ({exp_id})"
            # 绘制空心散点图（中心白色，边框彩色）
            plt.plot(df[x_col], df[y_col],
                     marker='o', markersize=6,
                     markerfacecolor='white',          # 中心白色不透明
                     markeredgewidth=1.2,
                     linestyle='-', linewidth=1.0,
                     label=label)
        except Exception as e:
            messagebox.showwarning("数据读取警告", f"读取文件 {os.path.basename(file_path)} 时出错：{e}")
    plt.xlabel('Cycle Number')
    plt.ylabel('Specific Discharge Capacity (mAh/g)')
    plt.title('Cycle Performance Comparison')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.show()

def plot_eis_comparison(records):
    """绘制EIS Nyquist图对比（-Z'' vs Z'）"""
    plt.figure(figsize=(10, 6))
    for exp_id, sample_id, file_path in records:
        try:
            df = safe_read_csv(file_path)
            # 自动识别频率、实部、虚部列
            freq_col = None
            zreal_col = None
            zimag_col = None
            for col in df.columns:
                col_lower = col.lower().replace("'", "").replace('"', '').replace(' ', '')
                if 'freq' in col_lower or '频率' in col:
                    freq_col = col
                elif "z'" in col_lower or 'zreal' in col_lower or 'z_real' in col_lower or '实部' in col:
                    zreal_col = col
                elif 'z"' in col_lower or 'zimag' in col_lower or 'z_imag' in col_lower or '虚部' in col:
                    zimag_col = col
            if zreal_col is None or zimag_col is None:
                # 尝试按常见顺序：第2列为实部，第3列为虚部
                if len(df.columns) >= 3:
                    zreal_col = df.columns[1]
                    zimag_col = df.columns[2]
                else:
                    raise ValueError("未找到阻抗实部/虚部列")
            # 转换为数值并删除无效行
            df[zreal_col] = pd.to_numeric(df[zreal_col], errors='coerce')
            df[zimag_col] = pd.to_numeric(df[zimag_col], errors='coerce')
            df = df.dropna(subset=[zreal_col, zimag_col])
            # Nyquist图通常以 -Z'' 为纵轴
            label = f"{sample_id} ({exp_id})"
            plt.plot(df[zreal_col], -df[zimag_col], marker='.', markersize=2, label=label)
        except Exception as e:
            messagebox.showwarning("数据读取警告", f"读取文件 {os.path.basename(file_path)} 时出错：{e}")
    plt.xlabel("Z' (ohm)")
    plt.ylabel('-Z" (ohm)')
    plt.title('EIS Nyquist 对比')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    ax = plt.gca()
    ax.set_aspect('equal', adjustable='box')  # 等比例坐标轴，更符合电化学习惯
    plt.tight_layout()
    plt.show()

def classify_test_type(test_type_str):
    """根据测试类型字符串返回类别：cycle / eis / other"""
    t = test_type_str.strip().lower()
    if '循环' in t or 'cycle' in t:
        return 'cycle'
    elif 'eis' in t or '阻抗' in t:
        return 'eis'
    else:
        return 'other'

# -------------------- 主界面 --------------------
class LocatorApp:
    def __init__(self, root):
        self.root = root
        root.title("实验数据定位器（支持多选对比）")
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

        btn_frame = ttk.Frame(query_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=10)
        ttk.Button(btn_frame, text="查询", command=self.search).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="清除条件", command=self.clear).pack(side="left", padx=10)

        # ---- 结果表格区域（支持多选） ----
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

        # ---- 底部操作按钮 ----
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

        if sample:
            mask &= self.df["样品编号"].str.contains(sample, na=False, case=False)
        if test_type:
            mask &= self.df["测试类型"].str.contains(test_type, na=False, case=False)
        if date_str:
            mask &= self.df["测试开始日期"].str.startswith(date_str, na=False)
        if filename:
            mask &= self.df["数据文件名"].str.contains(filename, na=False, case=False)

        results = self.df[mask]
        if results.empty:
            self.status_var.set("未找到匹配的实验")
            return

        for _, row in results.iterrows():
            exp_id = row["实验ID"]
            archive_path = get_archive_path(exp_id)
            self.tree.insert("", "end", values=(
                exp_id,
                row.get("样品编号", ""),
                row.get("测试类型", ""),
                row.get("测试开始日期", ""),
                row.get("数据文件名", ""),
                archive_path
            ))
        self.status_var.set(f"找到 {len(results)} 条记录")

    def clear(self):
        self.sample_var.set("")
        self.type_var.set("")
        self.date_var.set("")
        self.file_var.set("")
        self.search()

    def on_double_click(self, event):
        self.open_selected()

    def open_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先在表格中选择一条记录")
            return
        # 只打开第一个选中的文件夹（兼容原有行为）
        item = self.tree.item(selected[0])
        archive_path = item["values"][-1]
        open_folder(archive_path)

    def compare_curves(self):
        """对比选中的多条实验数据"""
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("缺少依赖", "对比功能需要 matplotlib 库。请运行：pip install matplotlib")
            return

        selected_items = self.tree.selection()
        if len(selected_items) < 2:
            messagebox.showwarning("选择不足", "请至少选择两个实验进行对比（Ctrl+点击多选）")
            return

        # 提取选中的记录信息：实验ID, 样品编号, 测试类型, 数据文件名, 归档路径
        records = []
        for item_id in selected_items:
            values = self.tree.item(item_id)["values"]
            exp_id, sample_id, test_type, _, data_filename, archive_path = values
            file_path = os.path.join(archive_path, "raw", data_filename)
            if not os.path.exists(file_path):
                messagebox.showerror("文件缺失", f"找不到数据文件：{file_path}")
                return
            records.append((exp_id, sample_id, test_type, file_path))

        # 判断测试类型大类是否一致
        categories = [classify_test_type(rec[2]) for rec in records]
        unique_cats = set(categories)
        if 'other' in unique_cats or len(unique_cats) != 1:
            messagebox.showerror("类型不匹配", "所选实验的测试类型不一致，请仅选择同一类型（如均为循环类或均为EIS类）")
            return

        cat = unique_cats.pop()
        if cat == 'cycle':
            plot_cycle_comparison([(rec[0], rec[1], rec[3]) for rec in records])
        elif cat == 'eis':
            plot_eis_comparison([(rec[0], rec[1], rec[3]) for rec in records])
        else:
            messagebox.showerror("不支持的类型", "当前版本仅支持循环类数据和EIS数据的对比")

if __name__ == "__main__":
    root = tk.Tk()
    app = LocatorApp(root)
    root.mainloop()