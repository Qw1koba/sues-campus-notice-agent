#!/usr/bin/env python3
"""Render the agent workflow used in the report."""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

matplotlib.rcParams["font.sans-serif"] = ["Arial Unicode MS", "Songti SC", "STHeiti"]
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "figures" / "architecture.png"


def box(ax, x, y, width, height, title, body, color, text_color="#17223b"):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.015,rounding_size=0.025",
        linewidth=1.2,
        edgecolor=color,
        facecolor=color + "18",
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height * 0.64,
        title,
        ha="center",
        va="center",
        fontsize=11,
        weight="bold",
        color=text_color,
    )
    ax.text(
        x + width / 2,
        y + height * 0.29,
        body,
        ha="center",
        va="center",
        fontsize=8.2,
        color="#5f6f89",
        linespacing=1.45,
    )


def arrow(ax, start, end, color="#8b9ab3"):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.1,
            color=color,
        )
    )


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13.5, 5.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.02,
        0.94,
        "校讯行动助手：端到端工作流",
        fontsize=17,
        weight="bold",
        color="#17223b",
    )
    ax.text(
        0.02,
        0.88,
        "本地模型与确定性工具协作；低置信度和高风险输入进入人工确认",
        fontsize=9.5,
        color="#6b7890",
    )

    box(ax, 0.025, 0.47, 0.13, 0.27, "① 输入", "粘贴文本\nTXT / DOCX / PDF", "#2457e6")
    box(ax, 0.185, 0.47, 0.14, 0.27, "② 输入校验", "长度、格式\nZIP 安全策略", "#5d6f93")
    box(ax, 0.355, 0.47, 0.14, 0.27, "③ 垃圾门禁", "英文 SMS 模型\n中文敏感词规则", "#c57913")
    box(ax, 0.525, 0.47, 0.14, 0.27, "④ 通知分流", "TF-IDF + 逻辑回归\n业务词保护规则", "#2457e6")
    box(ax, 0.695, 0.47, 0.14, 0.27, "⑤ 信息抽取", "日期、时间、材料\n动作、对象、风险", "#16866b")
    box(ax, 0.865, 0.47, 0.11, 0.27, "⑥ 决策", "自动完成 /\n人工复核", "#7c4dd8")

    for start, end in [
        ((0.155, 0.605), (0.185, 0.605)),
        ((0.325, 0.605), (0.355, 0.605)),
        ((0.495, 0.605), (0.525, 0.605)),
        ((0.665, 0.605), (0.695, 0.605)),
        ((0.835, 0.605), (0.865, 0.605)),
    ]:
        arrow(ax, start, end)

    box(ax, 0.535, 0.08, 0.18, 0.23, "行动清单", "检查对象、截止时间、材料\n逐项待办", "#16866b")
    box(ax, 0.76, 0.08, 0.2, 0.23, "外部产物", "ICS 日历 / Markdown\n本地审计 JSON", "#16866b")
    box(ax, 0.255, 0.08, 0.22, 0.23, "人工确认", "低置信度、待定时间\n敏感信息或资金风险", "#c43d4f")
    arrow(ax, (0.93, 0.47), (0.93, 0.31))
    arrow(ax, (0.90, 0.195), (0.76, 0.195))
    arrow(ax, (0.365, 0.47), (0.365, 0.31), "#c43d4f")

    ax.text(
        0.02,
        0.015,
        "说明：系统不代替用户登录、报名、缴费或提交材料；所有高风险决定保留人工确认。",
        fontsize=8.2,
        color="#7b879d",
    )
    fig.tight_layout()
    fig.savefig(OUTPUT, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
