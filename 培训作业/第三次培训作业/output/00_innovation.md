# 创新点（可验证）

1. **类型条件风化因子反演 + 多方法 MAE 对照**  
   对高钾/铅钡分别估计风化因子并归一化反演风化前成分；相对无校正，高钾 MAE 提升约 56.2%，铅钡约 54.7%。  
   证据：`q1_method_compare.csv` / `q1_method_compare.png`；预测表 `q1_preweather_predictions.csv`（32 条）。

2. **可解释化学规则与学习模型双轨互证**  
   PbO+BaO 阈值规则与决策树/随机森林/SVM 在留一法下均达准确率 1.000，规则与 RF 对未知样本完全一致，说明主分界可由助熔剂氧化物解释，而非黑箱偶然拟合。  
   证据：`q2_method_compare.csv` / `q2_method_compare.png`，`q2_feature_importance.png`（Top：PbO、BaO、SiO2、K2O、CaO），`q3_predictions.csv`。

3. **未知样本概率—翻转率—训练留一稳定性三重证据**  
   8 个未知样本判定为高钾 3、铅钡 5；平均置信度 0.933，最低 0.840；5% 相对噪声平均翻转率 0.000，训练 LOO 稳定比例均值 1.000。  
   证据：`q3_rf_proba.png`，`q3_flip_rate.png`，`q3_sensitivity_flip.csv`，`q3_loo_train_stability.csv`。

4. **Spearman 网络 + Mantel / |Δr| 的相关结构差异检验**  
   高钾显著相关对 32，铅钡 40；Mantel r=0.128（p=0.205）显示整体相似性有限；最大结构差为 Al2O3–SiO2（高钾 r=-0.831，铅钡 r=+0.425，|Δr|=1.255）。  
   证据：`q4_corr_diff_heatmap.png`，`q4_top_diff_pairs.png`，`q4_pair_diff_ranked.csv`。

5. **风化分层准确率与噪声蒙特卡洛闭环**  
   全体/风化/无风化子集准确率均为 1.000；σ=0.08 相对噪声 MC（n=200）准确率均值 1.000，P05–P95 均为 1.000。  
   证据：`adv_weather_stratified_acc.csv` / `.png`，`adv_mc_acc_hist.png`，`robust_mc_summary.json`。
