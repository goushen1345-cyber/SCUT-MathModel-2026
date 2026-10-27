# 四问整体框架图 v3

按本轮用户三张截图修改v2：删除底部结算说明、层间文字中的“，先预测再调度”及两处“目标：”；目标栏剩余文字与普通节点使用相同10pt粗体（中文SimHei），保持居中；收紧底部留白。保留v1/v2。

来源和箭头语义沿用../model-framework-v2/README.md及既有四问正文，本轮仅改图面。不改变模型、数据、研究状态或完整论文。

复现：在仓库根目录运行 python projects/2026-C/paper/figures/model-framework-v3/build.py。TikZ/XeLaTeX/Poppler生成矢量PDF、300 dpi灰度PNG和150 dpi预览；源码framework.tex，输入输出哈希manifest.json。

已实际查看最终预览，删除内容无残留、目标栏字体统一且无重叠裁切；编译无Overfull/Undefined/Error。未检查完整论文嵌入页，未进行人类计时试读。图前图后建议与解释边界沿用v2。
