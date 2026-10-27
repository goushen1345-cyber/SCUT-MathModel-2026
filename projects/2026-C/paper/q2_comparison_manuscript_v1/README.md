# 含问题二候选比较的论文草稿

论文草稿_含问题二候选比较.pdf共17页；同名.tex为主源文件。原问题一14页内容及排版保留，新增第8.2节为第15—17页。用户本轮授权记录权重并融入论文、实跑比较与据证据选方案，依据state/decisions.md的047、048、049。

新增内容包括：独立负载/PV预测、实际等权与系数来源、参数选择、误差余量公式、共同运行/结算条件、四方案费用表与选择理由、月份差异和多订代价。表4在第16页，图7在第17页。完整Q2年度调度结果、指定日提交内容、后续敏感性验证尚未完成，本稿不称最终论文。

源章节在sections/question2_comparison.tex，18个数值宏在q2_values.tex；原结果宏result_values.tex及原源章保留。新图figures/q2_cost_and_months.pdf来自真实比较图Q2-F01，PNG及另一支撑图位于questions/Q2/runs/20260911-four-candidates-v1/figures-v2。准确输入与文件指纹、构建命令见build_record.json。

重新编译（在本目录，使用已安装MiKTeX；修改后须重新检查页面）：

```text
xelatex --disable-installer -interaction=nonstopmode -halt-on-error -no-pdf -output-directory=build 论文草稿_含问题二候选比较.tex
xelatex --disable-installer -interaction=nonstopmode -halt-on-error -no-pdf -output-directory=build 论文草稿_含问题二候选比较.tex
xdvipdfmx -q -o 论文草稿_含问题二候选比较.pdf build/论文草稿_含问题二候选比较.xdv
pdftoppm -r 120 -png 论文草稿_含问题二候选比较.pdf preview/page
```

已实际查看新增15—17页及14页衔接，第10页求和符号另核对；前14页和原稿渲染像素完全一致。qa.json记录实际页面、数字、颜色、引用与字符边界检查；生成PDF不等于科学论证或人工审查通过，当前人工待阅。不会为本次写作冻结问题或推进Q3。
