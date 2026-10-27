# 问题一候选03/04/10比较复现

执行授权：Q1-TRIAL-026。用户报告：comparison_report.md；完整研究记录：../../report.md；论文证据：../../../../paper_evidence/Q1.md。

## 文件
- protocol.json：首次运行前固定的共同条件和有限参数范围。
- compare.py：54次规则计算和一次LP，保存全部明细、选优结果、配对差额和求解证书。
- verify.py：不导入主计算的独立检查器，使用标准库Decimal和原XLSX XML核对来源、逐段物理约束、费用及LP对偶证书。
- check_examples.py：三个手算规模的LP检查，输出analytic_checks.json。
- present.py：只读取结果做解释统计和代码图，不执行模型。
- outputs/：第一次主要运行的55份策略、参数全表、成本比较、四小时汇总、核查和证据。
- reproduction/：一次完整复现。59份核心CSV与首次一致；计时与运行时间戳不要求一致。
- figures-v4/：最终两幅PDF/PNG及来源/渲染检查。figures、figures-v2为早期排版版本，figures-v3为边界检查中止的部分输出，不作为正式交付。

## 执行
从本项目根目录运行；主计算和作图使用已安装E:/Anaconda/python.exe（Python3.13.5、numpy2.5.1、scipy1.18.0、matplotlib3.11.1）。独立检查使用捆绑Python3.12.14，仅标准库。中文字体C:/Windows/Fonts/simsun.ttc。

    E:/Anaconda/python.exe -X utf8 questions/Q1/runs/20260911-compare-v1/compare.py --output reproduction-new
    C:/Users/Rog/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -X utf8 questions/Q1/runs/20260911-compare-v1/verify.py --output reproduction-new
    E:/Anaconda/python.exe -X utf8 questions/Q1/runs/20260911-compare-v1/present.py --figures figures-new

输出目录必须不存在；作图固定读取第一次outputs，避免重新试跑。check_examples.py固定输出outputs/analytic_checks.json，仅明确复核小例子时运行。本机沙箱可能需允许已有Anaconda加载DLL，无须安装软件。

## 边界与留痕
主比较只运行一个已知代表日；27组规则参数是同日择优，不是独立测试。工作假设、时段近似和未验证范围见报告。原数据与模板只读，无正式结果表填写、问题二模拟、主模型批准或冻结。
verify检查通过与图的AI视觉检查不代表人类核验。主比较数值没有因排版修订改变；最终主张取outputs和paper_evidence/Q1.md，旧图不混用。
