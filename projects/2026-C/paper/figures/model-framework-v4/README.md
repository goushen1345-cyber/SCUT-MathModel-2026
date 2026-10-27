# 四问整体模型框架图 v4

按2026-09-13用户授权，仅替换既有TikZ框架图的8处名称或短标签。黑白配色、节点位置、连线、字体、四层结构和其余说明保持原样，不增加研究内容或图内解释。

原源码：../model-framework-v3/framework.tex。v3 PDF与用户提供PDF及论文原fig/model.pdf的SHA256均为5bf295aa811189394ca0f2be04ae9f6e89c31bfeb7b1ff1d6263b5c20d741075。原稿保留于v3，本目录model_before_name_update.pdf另存替换前论文图资源。

改名：已知代表日→代表日供需与电价；供需分解→用电缺口与光伏余量；问题二标题中的周期预测→历史分项预测；问题三标题→融合预测与日内校正滚动规划；历史融合光伏预报→负载校正与光伏融合；动态安全准备→近期误差准备；一次订电方案→当天固定购电计划；日内调整方案→零点计划与日内调整。

复现：运行本目录build.py，使用TikZ、XeLaTeX、Poppler生成矢量PDF、300 dpi灰度PNG和150 dpi预览。已实际查看预览，文字居中，无重叠或裁切；编译无Overfull、Undefined、Error，保留工具版本及字体设置警告。

同名PDF同步至shumo_1/shumo_backup_20260913_003434/fig/model.pdf。当前main.tex与所引用sections内没有该图引用，故未改正文或自动插图，也未更新main.pdf。