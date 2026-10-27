# -*- coding: utf-8 -*-
"""
问题4：三架无人机（FY1~FY3）各投放1枚烟幕干扰弹，对M1进行干扰。
改进点：
1) 三架无人机的方位角限制 THETA_BOUNDS_DEG = [ (45,315), (175,375), (25,160) ]，内部允许>360°，
   用于搜索与GA，但在实际计算时将角度映射到 [0, 360) 再转弧度。
2) 在GA优化前，先做一次粗网格搜索（按 方向→速度→投放时间→引信时间 的顺序做贪心式逐机筛选），
   将粗搜到的最佳个体作为精英注入到GA初始种群，随后进行局部精细搜索。

实现说明：
- 采用“点遮蔽/线段”判定：对每一时刻t，若云团中心到“导弹M(t)→TARGET的线段”的最小距离≤R_CLOUD，且云团
  在导弹与目标之间（投影距离在[0, |TARGET-M(t)|]），则认为该时刻被有效遮蔽。
- 烟幕云团：起爆后形成球，半径R_CLOUD，云心以CLOUD_SINK_V向下匀速下沉，持续CLOUD_TAU秒。
- 硬约束：对每架无人机，若 t_rel + fuse > t_max_i 则判为不可行（适应度=0）。t_max_i 按“导弹x坐标首次小于
  无人机x坐标”的时刻近似计算（来自题意中的分析约束）。
- 仅干扰 M1；三架无人机初始坐标取题面：FY1(17800,0,1800), FY2(12000,1400,1400), FY3(6000,-3000,700)。

运行结果：
- 控制台打印：粗网格搜索进度、GA每代最优/均值适应度与覆盖时长、最终最优参数与目标值；
- 另保存优化过程中的最优适应度历史到 /mnt/data/q4_fit_history.npy；
- 保存最优方案下的覆盖布尔序列和时间轴到 /mnt/data/q4_best_covered.npy 与 /mnt/data/q4_t_grid.npy。

注：代码中包含足够的向量化以保证粗网格+GA能在合理时间内完成。
"""

# from __future__ import annotations
import math, random, time
import numpy as np

# =================== 场景常量 ===================
TARGET = np.array([0.0, 200.0, 5.0], dtype=float)  # 真目标下底面圆心
MISSILE_SPEED = 300.0  # m/s
R_CLOUD = 10.0         # 有效遮蔽半径
CLOUD_SINK_V = 3.0     # 云团下沉速度 (m/s)
CLOUD_TAU = 20.0       # 云团有效持续时间 (s)
G = 9.81
G_VEC = np.array([0.0, 0.0, -G], dtype=float)

# 三架无人机与 M1 初始位置（题面给定）
FY0 = np.array([
    [17800.0,     0.0, 1800.0],  # FY1
    [12000.0,  1400.0, 1400.0],  # FY2
    [ 6000.0, -3000.0,  700.0],  # FY3
], dtype=float)
M0 = np.array([20000.0, 0.0, 2000.0], dtype=float)  # 仅M1

N_DRONES = 3

# 决策变量范围
SPEED_LOWER, SPEED_UPPER = 70.0, 140.0
FUSE_LOWER, FUSE_UPPER   = 0.0, 10.0
# 角度边界（度），FY2允许到375°，实际计算时做 %360
THETA_BOUNDS_DEG = [ (45.0, 315.0), (175.0, 375.0), (25.0, 160.0) ]

# 时间离散
DT = 0.01  # s（兼顾精度与速度）

# =================== 工具函数 ===================

def unit(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.clip(n, eps, None)

# 导弹轨迹（直线等速指向TARGET）

def missile_trajectory(M0: np.ndarray, t_grid: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dir_to_target = ( -M0 ) / np.linalg.norm(M0)          # ← 指向原点
    M = M0[None, :] + MISSILE_SPEED * t_grid[:, None] * dir_to_target[None, :]
    vec_to_target = TARGET[None, :] - M
    U_hat = unit(vec_to_target)
    Dist = np.linalg.norm(vec_to_target, axis=1)
    return M, U_hat, Dist

# 无人机在t时刻的三维位置

def drone_pos_at(FY_init: np.ndarray, v: float, theta_deg_any: float, t: float) -> np.ndarray:
    theta = math.radians(theta_deg_any % 360.0)
    dir2 = np.array([math.cos(theta), math.sin(theta), 0.0], dtype=float)
    return FY_init + v * t * dir2

# 起爆点（抛体）：释放时刻t_rel，沿无人机速度方向抛出，tau后起爆

def explosion_point(P_rel: np.ndarray, v: float, theta_deg_any: float, fuse: float) -> np.ndarray:
    theta = math.radians(theta_deg_any % 360.0)
    V_rel = v * np.array([math.cos(theta), math.sin(theta), 0.0], dtype=float)
    return P_rel + V_rel * fuse + 0.5 * G_VEC * (fuse ** 2)

# 云团中心随时间（自起爆时刻tau起）

def cloud_center_over_slice(E: np.ndarray, tau: float, t_slice: np.ndarray) -> np.ndarray:
    sink = np.array([0.0, 0.0, -CLOUD_SINK_V], dtype=float)
    return E[None, :] + (t_slice - tau)[:, None] * sink[None, :]

# 视线“线段”遮蔽判定（矢量化）：
# 给定 M_sub (Tsub×3), U_hat_sub (Tsub×3), Dist_sub (Tsub,), 以及 C_sub (Tsub×3)
# 判定 C_sub 是否在导弹→目标的线段附近（半径R_CLOUD），且投影在 [0, Dist_sub]

def segment_block_bool(M_sub: np.ndarray, U_hat_sub: np.ndarray, Dist_sub: np.ndarray, C_sub: np.ndarray,
                       R: float = R_CLOUD) -> np.ndarray:
    delta = C_sub - M_sub                       # Tsub×3
    dot = np.sum(delta * U_hat_sub, axis=1)     # 投影长度（沿 M→TARGET 的方向）
    # 线段条件：0 <= dot <= |TARGET - M|
    mask_ray = (dot >= 0.0) & (dot <= Dist_sub + 1e-12)
    # 垂距平方 <= R^2
    perp2 = np.sum(delta * delta, axis=1) - dot * dot
    return mask_ray & (perp2 <= R * R + 1e-12)

# 计算时间地平线（导弹到达TARGET的时间）

def compute_horizon(M0: np.ndarray) -> float:
    D = np.linalg.norm(TARGET - M0)
    return float(D / MISSILE_SPEED)

# 近似约束时刻 t_max_i：导弹x坐标首次小于无人机x坐标的时刻
# 解 Mx(t) = Dx(t) 的首次交点；若无交点，取地平线T_end

def t_max_cross_x(i: int, v_i: float, theta_deg_any: float, T_end: float, Mx0: float, Vmx: float) -> float:
    Dx0 = FY0[i, 0]
    Vdx = v_i * math.cos(math.radians(theta_deg_any % 360.0))
    denom = Vmx - Vdx
    if abs(denom) < 1e-9:
        return T_end
    t_cross = (Dx0 - Mx0) / denom  # 使 Mx(t) = Dx(t)
    if t_cross <= 0:
        # 若初始时就 Mx<=Dx 或交点在过去，则约束放宽为地平线
        return T_end
    return float(min(t_cross, T_end))

# 计算单枚炸点对整段时间的遮蔽布尔序列（长度T）

def single_bomb_cover_bool(i: int, v_i: float, theta_deg_any: float, t_rel: float, fuse: float,
                           t_grid: np.ndarray, M: np.ndarray, U_hat: np.ndarray, Dist: np.ndarray) -> np.ndarray:
    T_end = t_grid[-1]
    tau = t_rel + fuse
    if tau > T_end:
        return np.zeros_like(t_grid, dtype=bool)
    # 释放点与起爆点
    P_rel = drone_pos_at(FY0[i], v_i, theta_deg_any, t_rel)
    E = explosion_point(P_rel, v_i, theta_deg_any, fuse)
    # —— 新增：起爆点必须在地面以上 ——
    if E[2] <= 0.0:
        return np.zeros_like(t_grid, dtype=bool)

    # 云团有效区间：寿命、落地、全局上界 三者取最小
    t_cloud_end = min(T_end, tau + CLOUD_TAU, tau + E[2] / CLOUD_SINK_V)
    if t_cloud_end <= tau:
        return np.zeros_like(t_grid, dtype=bool)

    # 云团有效区间
    t0 = int(math.ceil(tau / DT))
    t1 = int(math.floor(min(tau + CLOUD_TAU, T_end) / DT))
    if t1 < t0:
        return np.zeros_like(t_grid, dtype=bool)
    t_slice = t_grid[t0:t1+1]
    C_sub = cloud_center_over_slice(E, tau, t_slice)           # (Tsub×3)
    M_sub = M[t0:t1+1, :]                                      # (Tsub×3)
    U_sub = U_hat[t0:t1+1, :]                                   # (Tsub×3)
    D_sub = Dist[t0:t1+1]                                       # (Tsub,)
    cond_sub = segment_block_bool(M_sub, U_sub, D_sub, C_sub)   # (Tsub,)
    ans = np.zeros_like(t_grid, dtype=bool)
    ans[t0:t1+1] = cond_sub
    return ans

# 给定完整方案计算适应度（覆盖总时长）与覆盖序列

def evaluate_plan(v: np.ndarray, theta_deg: np.ndarray, t_rel: np.ndarray, fuse: np.ndarray,
                   t_grid: np.ndarray, M: np.ndarray, U_hat: np.ndarray, Dist: np.ndarray,
                   Mx0: float, Vmx: float) -> tuple[float, np.ndarray]:
    # 硬约束：任一 i 若 tau > t_max_i 则适应度=0
    T_end = t_grid[-1]
    for i in range(N_DRONES):
        tmax_i = t_max_cross_x(i, float(v[i]), float(theta_deg[i]), T_end, Mx0, Vmx)
        if float(t_rel[i] + fuse[i]) > tmax_i + 1e-12:
            return 0.0, np.zeros_like(t_grid, dtype=bool)

    covered = np.zeros_like(t_grid, dtype=bool)
    for i in range(N_DRONES):
        c_i = single_bomb_cover_bool(i, float(v[i]), float(theta_deg[i]), float(t_rel[i]), float(fuse[i]),
                                     t_grid, M, U_hat, Dist)
        covered |= c_i
    total = float(np.count_nonzero(covered) * DT)
    return total, covered

# =================== 粗网格搜索（贪心式逐机加入） ===================

def coarse_greedy_search(t_grid: np.ndarray, M: np.ndarray, U_hat: np.ndarray, Dist: np.ndarray,
                         Mx0: float, Vmx: float,
                         angle_step: float = 5.0,
                         speed_set: list[float] | None = None,
                         trel_step: float = 2.0,
                         fuse_step: float = 2.0,
                         verbose: bool = True):
    if speed_set is None:
        # 覆盖70~140，含140
        speed_set = [70.0, 90.0, 110.0, 130.0, 140.0]

    T_end = t_grid[-1]
    covered = np.zeros_like(t_grid, dtype=bool)

    v_best = np.zeros(N_DRONES)
    th_best = np.zeros(N_DRONES)
    rel_best = np.zeros(N_DRONES)
    fuse_best = np.zeros(N_DRONES)

    total_best = 0.0

    for i in range(N_DRONES):
        th_low, th_high = THETA_BOUNDS_DEG[i]
        # 生成角度网格（允许>360，在计算时做%360）
        if th_high >= th_low:
            angs = np.arange(th_low, th_high + 1e-9, angle_step)
        else:
            # 兜底（本题用不到）
            angs = np.concatenate([
                np.arange(th_low, 360.0, angle_step),
                np.arange(0.0, th_high + 1e-9, angle_step)
            ])

        best_i = {
            'score': -1.0,
            'v': None, 'th': None, 'rel': None, 'fuse': None,
            'cover_add': None
        }
        cnt_eval = 0
        t0 = time.time()
        for th in angs:
            for v in speed_set:
                # 约束时间上界（快速剪枝）
                tmax_i = t_max_cross_x(i, v, th, T_end, Mx0, Vmx)
                # 粗粒度时间/引信枚举
                for t_rel in np.arange(0.0, T_end + 1e-9, trel_step):
                    # 若释放太晚，直接跳过
                    if t_rel > tmax_i:
                        break
                    # 起爆时间不超过 tmax_i
                    # 按 fuse_step 扫描
                    fuse_max_feasible = min(FUSE_UPPER, max(0.0, tmax_i - t_rel))
                    if fuse_max_feasible < FUSE_LOWER + 1e-9:
                        continue
                    for fuse in np.arange(FUSE_LOWER, fuse_max_feasible + 1e-9, fuse_step):
                        cnt_eval += 1
                        c_i = single_bomb_cover_bool(i, v, th, t_rel, fuse, t_grid, M, U_hat, Dist)
                        # 与已有覆盖做并集
                        new_covered = covered | c_i
                        total = float(np.count_nonzero(new_covered) * DT)
                        if total > best_i['score'] + 1e-12:
                            best_i.update({'score': total, 'v': v, 'th': th, 'rel': t_rel,
                                           'fuse': fuse, 'cover_add': c_i})
        # 固定第i架的最优
        if best_i['v'] is None:
            # 极端情况下没有可行（几乎不会发生），保持默认
            if verbose:
                print(f"[COARSE] Drone#{i}: 未找到可行解，跳过")
            continue
        covered |= best_i['cover_add']
        v_best[i] = best_i['v']
        th_best[i] = best_i['th']
        rel_best[i] = best_i['rel']
        fuse_best[i] = best_i['fuse']
        total_best = best_i['score']
        if verbose:
            dt = time.time() - t0
            print(f"[COARSE] Drone#{i}: best_total={total_best:.2f}s | v={v_best[i]:.1f} m/s, "
                  f"θ={th_best[i]:.1f}°, t_rel={rel_best[i]:.2f}s, fuse={fuse_best[i]:.2f}s | evals≈{cnt_eval}, "
                  f"time={dt:.1f}s")

    return (v_best, th_best, rel_best, fuse_best), covered

# =================== GA 相关 ===================

class GA:
    def __init__(self, t_grid, M, U_hat, Dist, Mx0, Vmx,
                 pop_size=120, elite_frac=0.2, cx_prob=0.9, mut_prob=0.9,
                 n_gen=200, patience=35, max_restarts=5, keep_frac_on_restart=0.25,
                 sigma_decay=0.9, seed=42):
        self.t_grid = t_grid
        self.M = M
        self.U_hat = U_hat
        self.Dist = Dist
        self.Mx0 = Mx0
        self.Vmx = Vmx
        self.pop_size = pop_size
        self.elite_frac = elite_frac
        self.cx_prob = cx_prob
        self.mut_prob = mut_prob
        self.n_gen = n_gen
        self.patience = patience
        self.max_restarts = max_restarts
        self.keep_frac_on_restart = keep_frac_on_restart
        self.sigma_decay = sigma_decay
        random.seed(seed); np.random.seed(seed)

    def _rand_theta(self, low_deg, high_deg):
        return random.uniform(low_deg, high_deg)

    def _rand_speed(self):
        return random.uniform(SPEED_LOWER, SPEED_UPPER)

    def _rand_time(self, T_end):
        return random.uniform(0.0, T_end)

    def init_population(self, elite_seed=None):
        T_end = self.t_grid[-1]
        pop = []
        if elite_seed is not None:
            pop.append(elite_seed)
        # 其余随机
        while len(pop) < self.pop_size:
            v = np.array([self._rand_speed() for _ in range(N_DRONES)], dtype=float)
            th = np.array([self._rand_theta(*THETA_BOUNDS_DEG[i]) for i in range(N_DRONES)], dtype=float)
            rel = np.array([self._rand_time(T_end) for _ in range(N_DRONES)], dtype=float)
            fuse = np.array([random.uniform(FUSE_LOWER, FUSE_UPPER) for _ in range(N_DRONES)], dtype=float)
            pop.append((v, th, rel, fuse))
        return pop

    @staticmethod
    def _uniform_crossover(p1, p2):
        v1, th1, r1, f1 = p1
        v2, th2, r2, f2 = p2
        mask_v = np.random.rand(N_DRONES) < 0.5
        child_v = np.where(mask_v, v1, v2)
        child_th = np.where(mask_v, th1, th2)
        mask_b = np.random.rand(N_DRONES) < 0.5
        child_r = np.where(mask_b, r1, r2)
        child_f = np.where(mask_b, f1, f2)
        return (child_v, child_th, child_r, child_f)

    @staticmethod
    def _mutate(ind, T_end,
                sigma_v=2.0, sigma_deg=2.0, sigma_r=0.5, sigma_f=0.5, p=0.5):
        v, th, r, f = ind
        v = v.copy(); th = th.copy(); r = r.copy(); f = f.copy()
        if np.random.rand() < p:
            v += np.random.normal(0.0, sigma_v, size=v.shape)
            v = np.clip(v, SPEED_LOWER, SPEED_UPPER)
        if np.random.rand() < p:
            th += np.random.normal(0.0, sigma_deg, size=th.shape)
            # 只需保持在给定区间内（允许>360，在计算时取%360）
            for i in range(N_DRONES):
                lo, hi = THETA_BOUNDS_DEG[i]
                th[i] = float(np.clip(th[i], lo, hi))
        if np.random.rand() < p:
            r += np.random.normal(0.0, sigma_r, size=r.shape)
        if np.random.rand() < p:
            f += np.random.normal(0.0, sigma_f, size=f.shape)
        r = np.clip(r, 0.0, T_end)
        f = np.clip(f, FUSE_LOWER, FUSE_UPPER)
        return (v, th, r, f)

    def _reseed_around_elites(self, elites, keep_k, sigmas):
        T_end = self.t_grid[-1]
        sv, sd, sr, sf = sigmas
        new_pop = [ (e[0].copy(), e[1].copy(), e[2].copy(), e[3].copy()) for e in elites[:keep_k] ]
        need = self.pop_size - keep_k
        e_cnt = len(elites)
        for i in range(need):
            base = elites[i % e_cnt]
            v, th, r, f = base
            v = (v + np.random.normal(0.0, sv, size=v.shape)).clip(SPEED_LOWER, SPEED_UPPER)
            th = th + np.random.normal(0.0, sd, size=th.shape)
            # clip到边界但允许>360（在计算时再%360）
            for k in range(N_DRONES):
                lo, hi = THETA_BOUNDS_DEG[k]
                th[k] = float(np.clip(th[k], lo, hi))
            r = (r + np.random.normal(0.0, sr, size=r.shape)).clip(0.0, T_end)
            f = (f + np.random.normal(0.0, sf, size=f.shape)).clip(FUSE_LOWER, FUSE_UPPER)
            new_pop.append((v, th, r, f))
        return new_pop

    def run(self, pop, verbose=True):
        elite_k = max(1, int(self.pop_size * self.elite_frac))
        best = None
        best_fit = -1e18
        best_cov = None
        fit_history = []
        no_improve = 0
        restarts = 0
        sigmas = [3.0, 3.0, 0.3, 0.3]  # reseed 初始扰动

        for g in range(1, self.n_gen + 1):
            scores = np.zeros(self.pop_size)
            totals = np.zeros(self.pop_size)

            for i, ind in enumerate(pop):
                v, th, r, f = ind
                # 评估（适应度=覆盖总时长）
                total, _cov = evaluate_plan(v, th, r, f, self.t_grid, self.M, self.U_hat, self.Dist,
                                            self.Mx0, self.Vmx)
                scores[i] = total
                totals[i] = total

            idx_best = int(np.argmax(scores))
            gen_best = pop[idx_best]
            gen_best_fit = float(scores[idx_best])
            fit_history.append(gen_best_fit)

            if gen_best_fit > best_fit + 1e-12:
                best_fit = gen_best_fit
                total, cov = evaluate_plan(*gen_best, self.t_grid, self.M, self.U_hat, self.Dist,
                                           self.Mx0, self.Vmx)
                best = gen_best
                best_cov = cov
                no_improve = 0
            else:
                no_improve += 1

            if verbose:
                print(f"[GA] Gen {g:03d}: best={gen_best_fit:.3f} s, mean={scores.mean():.3f} s, no_improve={no_improve}")

            # 停滞-部分重启
            if no_improve >= self.patience and restarts < self.max_restarts:
                keep_k = max(1, int(self.pop_size * self.keep_frac_on_restart))
                elite_idx = np.argsort(-scores)[:keep_k]
                elites = [ (pop[i][0].copy(), pop[i][1].copy(), pop[i][2].copy(), pop[i][3].copy()) for i in elite_idx ]
                pop = self._reseed_around_elites(elites, keep_k, sigmas)
                no_improve = 0
                restarts += 1
                # 逐步减小重启扰动
                sigmas = [s * self.sigma_decay for s in sigmas]
                if verbose:
                    print(f"[GA-RESTART] at Gen {g}, keep {keep_k}/{self.pop_size}, new sigmas={sigmas}, restart #{restarts}")
                continue

            # 精英+交叉+变异
            elite_idx = np.argsort(-scores)[:elite_k]
            elites = [ (pop[i][0].copy(), pop[i][1].copy(), pop[i][2].copy(), pop[i][3].copy()) for i in elite_idx ]

            # 赌轮选择概率（避免负值）
            probs = scores - scores.min() + 1e-12
            probs = probs / probs.sum()
            def pick():
                return pop[np.random.choice(self.pop_size, p=probs)]

            children = []
            while len(children) + len(elites) < self.pop_size:
                if np.random.rand() < self.cx_prob:
                    c = self._uniform_crossover(pick(), pick())
                else:
                    p = pick(); c = (p[0].copy(), p[1].copy(), p[2].copy(), p[3].copy())
                if np.random.rand() < self.mut_prob:
                    c = self._mutate(c, self.t_grid[-1])
                # 角度保持在边界内（但允许>360，计算时会%360）
                for k in range(N_DRONES):
                    lo, hi = THETA_BOUNDS_DEG[k]
                    c[1][k] = float(np.clip(c[1][k], lo, hi))
                children.append(c)

            pop = elites + children

        return best, best_fit, best_cov, np.array(fit_history, dtype=float)

# =================== 主函数 ===================

def main():
    np.set_printoptions(suppress=True, linewidth=160)
    # 时间轴与导弹轨迹
    T_end = compute_horizon(M0)
    t_grid = np.arange(0.0, T_end + 1e-12, DT)
    M, U_hat, Dist = missile_trajectory(M0, t_grid)
    # x 方向速度（用于 t_max 近似约束）
    dir_to_origin = (-M0) / np.linalg.norm(M0)
    Vmx = MISSILE_SPEED * float(dir_to_origin[0])
    Mx0 = float(M0[0])

    print(f"Time horizon T_end = {T_end:.3f} s, steps = {len(t_grid)} (DT={DT})")

    # ====== 粗网格搜索（贪心逐机） ======
    t_start = time.time()
    coarse_best, covered_after_coarse = coarse_greedy_search(
        t_grid, M, U_hat, Dist, Mx0, Vmx,
        angle_step=5.0, speed_set=[70,90,110,130,140], trel_step=2.0, fuse_step=2.0, verbose=True
    )
    v0, th0, rel0, fuse0 = coarse_best
    total0, cov0 = evaluate_plan(v0, th0, rel0, fuse0, t_grid, M, U_hat, Dist, Mx0, Vmx)
    print("\n[COARSE] 粗搜总覆盖=%.3f s" % total0)
    print("[COARSE] 初始个体：")
    for i in range(N_DRONES):
        print(f"  Drone#{i+1}: v={v0[i]:.1f} m/s, θ={th0[i]:.1f}°, t_rel={rel0[i]:.2f}s, fuse={fuse0[i]:.2f}s")
    print("粗网格用时：%.1f s" % (time.time() - t_start))

    # ====== GA 局部细化 ======
    ga = GA(t_grid, M, U_hat, Dist, Mx0, Vmx,
            pop_size=140, elite_frac=0.2, cx_prob=0.9, mut_prob=0.9,
            n_gen=240, patience=45, max_restarts=6, keep_frac_on_restart=0.25,
            sigma_decay=0.9, seed=2025)

    elite_seed = (v0.copy(), th0.copy(), rel0.copy(), fuse0.copy())
    pop = ga.init_population(elite_seed=elite_seed)

    best, best_fit, best_cov, fit_hist = ga.run(pop, verbose=True)

    v_b, th_b, rel_b, fuse_b = best
    total_b, cov_b = evaluate_plan(v_b, th_b, rel_b, fuse_b, t_grid, M, U_hat, Dist, Mx0, Vmx)

    print("\n===== 问题4 最优解（粗搜 + GA） =====")
    print(f"覆盖总时长 = {total_b:.3f} s")
    for i in range(N_DRONES):
        print(f"无人机FY{i+1}: v={v_b[i]:.2f} m/s, θ={th_b[i]%360:.2f}°, t_rel={rel_b[i]:.2f} s, fuse={fuse_b[i]:.2f} s")
    # 记录算法总运行时间并打印
    t_end = time.time()
    print(f"算法总运行时间：{t_end - t_start:.2f} 秒")
    # 保存过程与结果
    np.save('results/q4_fit_history.npy', fit_hist)
    np.save('results/q4_best_covered.npy', cov_b.astype(np.int8))
    np.save('results/q4_t_grid.npy', t_grid)
    np.save('results/q4_solution_v.npy', v_b)
    np.save('results/q4_solution_theta_deg.npy', th_b)
    np.save('results/q4_solution_trel.npy', rel_b)
    np.save('results/q4_solution_fuse.npy', fuse_b)
    print("已保存：results/q4_*.npy 一组文件（fit_history / best_covered / t_grid / solution参数）")

if __name__ == '__main__':
    main()
