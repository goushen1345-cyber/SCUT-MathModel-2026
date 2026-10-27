# Create a new script that adds "stagnation-triggered partial restart around elites"

# -*- coding: utf-8 -*-
# GA refinement with heavy penalty on same-drone release gaps < 1s.
# Plus: if best doesn't improve for PATIENCE generations, keep a fraction of elites
# and re-seed the rest around elites (partial restart), then continue GA.
import math, random, numpy as np

# =================== Scenario params ===================
TARGET = np.array([0.0, 200.0, 5.0])
MISSILE_SPEED = 300.0
R_CLOUD = 10.0
CLOUD_SINK_V = 3.0
CLOUD_TAU = 20.0
G = 9.81
g_vec = np.array([0.0, 0.0, -G])

# -------- Time resolution (based on your request) --------
DT = 0.005  # finer grid
RELEASE_T_MIN_GAP = 1.0  # for penalty only
FUSE_LOWER, FUSE_UPPER = 0.0, 10.0
SPEED_LOWER, SPEED_UPPER = 70.0, 140.0
LAMBDA_GAP = 1000.0  # heavy penalty weight

# =================== Initial positions ===================
FY0 = np.array([
    [17800.0,     0.0, 1800.0],
    [12000.0,  1400.0, 1400.0],
    [ 6000.0, -3000.0,  700.0],
    [11000.0,  2000.0, 1800.0],
    [13000.0, -2000.0, 1300.0],
], dtype=float)

M0 = np.array([
    [20000.0,     0.0, 2000.0],
    [19000.0,   600.0, 2100.0],
    [18000.0,  -600.0, 1900.0],
], dtype=float)

N_DRONES = FY0.shape[0]
N_MISSILES = M0.shape[0]

# =================== Provided init ===================
v_init = np.array([125.0, 115.0, 140.0, 110.0, 130.0], dtype=float)
theta_init_deg = np.array([180.0, 240.0, 87.0, 294.0, 132.0], dtype=float)
bombs_base = [
    (1, 5.0, 5.0),
    (2, 22.0, 1.5),
    (2, 18.0, 2.5),
    (4, 15.0, 6.0),
    (2, 19.0, 3.0),
    (3, 6.0, 10.0),
    (1, 6.0, 7.5),
    (1, 7.0, 7.0),
    (0, 1.0, 4.0),
    (0, 0.0, 0.0),
    (0, 4.0, 5.0),
    (4, 13.0, 4.0),
]

# =================== Helpers ===================
def unit(v, eps=1e-9):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.clip(n, eps, None)

def missile_trajectories(m_init, t_grid, speed=MISSILE_SPEED):
    M0 = m_init.copy()
    dirs = unit(-M0)
    M = M0[:, None, :] + (speed * t_grid[None, :, None]) * dirs[:, None, :]
    N_hat = unit(TARGET[None, None, :] - M)
    return M, N_hat

def drone_dir(theta_rad):
    return np.array([math.cos(theta_rad), math.sin(theta_rad), 0.0])

def drone_pos_at(dr_init, v, theta_rad, t):
    return dr_init + v * t * drone_dir(theta_rad)

def explosion_point(P_release, V_release, fuse):
    return P_release + V_release * fuse + 0.5 * g_vec * (fuse ** 2)

def cloud_center_at(E, tau, t_sub):
    sink = np.array([0.0, 0.0, -CLOUD_SINK_V])
    return E[None, :] + (t_sub - tau)[:, None] * sink[None, :]

def compute_horizon(m_init, speed=MISSILE_SPEED):
    dist = np.linalg.norm(m_init, axis=1)
    return float(np.max(dist / speed))

def gap_penalty(bomb_drone, bomb_release, min_gap=RELEASE_T_MIN_GAP):
    """Sum of deficits (min_gap - gap)+ across all pairs per drone."""
    pen = 0.0
    for d in range(N_DRONES):
        idx = np.where(bomb_drone == d)[0]
        if idx.size < 2: 
            continue
        times = np.sort(bomb_release[idx])
        gaps = np.diff(times)
        deficit = np.maximum(0.0, min_gap - gaps)
        pen += float(np.sum(deficit))
    return pen

# =================== Evaluate plan ===================
def evaluate_plan(v, theta_rad, bomb_drone, bomb_release, bomb_fuse, t_grid, M, N_hat):
    Mnum, Tn = M.shape[0], len(t_grid)
    covered = np.zeros((Mnum, Tn), dtype=bool)
    T_max = t_grid[-1]
    bomb_release = np.clip(bomb_release, 0.0, T_max)
    bomb_fuse = np.clip(bomb_fuse, 0.0, 10.0)

    for d_id, t_rel, fuse in zip(bomb_drone, bomb_release, bomb_fuse):
        tau = t_rel + fuse
        if tau > t_grid[-1]:
            continue

        P = drone_pos_at(FY0[d_id], v[d_id], theta_rad[d_id], t_rel)
        V_vec = v[d_id] * drone_dir(theta_rad[d_id])
        E = explosion_point(P, V_vec, fuse)  # [x_e, y_e, z_e]

        # —— 起爆点必须在地面以上
        if E[2] <= 0.0:
            continue

        # —— 云团有效到“寿命/落地/全局上限”的最早时刻
        t_end = min(tau + CLOUD_TAU, tau + E[2] / CLOUD_SINK_V, t_grid[-1])
        if t_end <= tau:
            continue

        j0 = int(np.ceil(tau / DT))
        j1 = int(np.floor(t_end / DT))
        t_sub = t_grid[j0:j1+1]
        C = cloud_center_at(E, tau, t_sub)
        M_sub = M[:, j0:j1+1, :]
        N_sub = N_hat[:, j0:j1+1, :]
        Dist_sub = np.linalg.norm(TARGET[None, None, :] - M_sub, axis=2)  # (M,len)

        delta = C[None, :, :] - M_sub
        dot   = np.sum(delta * N_sub, axis=2)      # 投影长度（沿 M->TARGET）
        delta2= np.sum(delta * delta, axis=2)
        perp2 = delta2 - dot * dot                 # 垂距^2（可加数值夹紧）
        # perp2 = np.maximum(perp2, 0.0)

        # —— 线段判定：0 <= dot <= Dist_sub ；同时在半径内
        cond = (perp2 <= (R_CLOUD**2) + 1e-12) & (dot >= -1e-12) & (dot <= Dist_sub + 1e-12)
        covered[:, j0:j1+1] |= cond

    total = float(np.count_nonzero(covered) * DT)
    penalty = gap_penalty(bomb_drone, bomb_release)
    fitness = total - LAMBDA_GAP * penalty
    return fitness, total, penalty, covered

# =================== Init population ===================
def seed_initial_population(pop_size, t_grid, with_speed=True, with_theta=True):
    T_max = t_grid[-1]
    base = list(bombs_base)
    # Add 2 random bombs for drone#3
    for _ in range(2):
        base.append((3, random.uniform(0.0, T_max), random.uniform(0.0, 10.0)))

    elite_v = v_init.copy()
    elite_theta = np.deg2rad(theta_init_deg.copy())
    bomb_drone = np.array([d for (d,_,_) in base], dtype=int)
    bomb_release = np.array([t for (_,t,_) in base], dtype=float)
    bomb_fuse = np.array([f for (_,_,f) in base], dtype=float)
    bomb_release = np.clip(bomb_release, 0.0, T_max)
    bomb_fuse = np.clip(bomb_fuse, 0.0, 10.0)

    pop = [(elite_v.copy(), elite_theta.copy(), bomb_release.copy(), bomb_fuse.copy())]

    for _ in range(pop_size - 1):
        v = elite_v.copy()
        th = elite_theta.copy()
        if with_speed:
            v += np.random.normal(0.0, 10.0, size=v.shape)
            v = np.clip(v, 70.0, 140.0)
        if with_theta:
            th += np.deg2rad(np.random.normal(0.0, 10.0, size=th.shape))
        rel = bomb_release.copy() + np.random.normal(0.0, 2.0, size=bomb_release.shape)
        fuse = bomb_fuse.copy() + np.random.normal(0.0, 1.0, size=bomb_fuse.shape)
        rel = np.clip(rel, 0.0, T_max)
        fuse = np.clip(fuse, 0.0, 10.0)
        pop.append((v, th, rel, fuse))
    return bomb_drone, pop

# =================== Genetic operators ===================
def uniform_crossover(p1, p2):
    v1, th1, r1, f1 = p1
    v2, th2, r2, f2 = p2
    mask_v = np.random.rand(len(v1)) < 0.5
    mask_b = np.random.rand(len(r1)) < 0.5
    child_v = np.where(mask_v, v1, v2)
    child_th = np.where(mask_v, th1, th2)
    child_r = np.where(mask_b, r1, r2)
    child_f = np.where(mask_b, f1, f2)
    return (child_v, child_th, child_r, child_f)

def mutate(ind, t_grid, sigma_v=2.0, sigma_deg=2.0, sigma_r=0.2, sigma_f=0.2, p=0.4):
    v, th, r, f = ind
    v = v.copy(); th = th.copy(); r = r.copy(); f = f.copy()
    T_max = t_grid[-1]
    if np.random.rand() < p:
        v += np.random.normal(0.0, sigma_v, size=v.shape)
        v = np.clip(v, 70.0, 140.0)
    if np.random.rand() < p:
        th += np.deg2rad(np.random.normal(0.0, sigma_deg, size=th.shape))
    if np.random.rand() < p:
        r += np.random.normal(0.0, sigma_r, size=r.shape)
    if np.random.rand() < p:
        f += np.random.normal(0.0, sigma_f, size=f.shape)
    r = np.clip(r, 0.0, T_max)
    f = np.clip(f, 0.0, 10.0)
    return (v, th, r, f)

# =================== Partial-restart helpers ===================
def reseed_around_elites(elites, keep_k, pop_size, t_grid,
                         sigma_v=10.0, sigma_deg=10.0, sigma_r=1.5, sigma_f=0.5):
    """Keep first keep_k elites, reinitialize the rest around elites with Gaussian noise."""
    T_max = t_grid[-1]
    new_pop = [ (e[0].copy(), e[1].copy(), e[2].copy(), e[3].copy()) for e in elites[:keep_k] ]
    need = pop_size - keep_k
    e_cnt = len(elites)
    for i in range(need):
        base = elites[i % e_cnt]
        v, th, r, f = base
        v = (v + np.random.normal(0.0, sigma_v, size=v.shape)).clip(SPEED_LOWER, SPEED_UPPER)
        th = th + np.deg2rad(np.random.normal(0.0, sigma_deg, size=th.shape))
        r = (r + np.random.normal(0.0, sigma_r, size=r.shape)).clip(0.0, T_max)
        f = (f + np.random.normal(0.0, sigma_f, size=f.shape)).clip(FUSE_LOWER, FUSE_UPPER)
        new_pop.append((v, th, r, f))
    return new_pop

# =================== GA loop (with stagnation-triggered restart) ===================
def run_ga(pop, bomb_owner, t_grid, M, N_hat, n_gen=300, elite_frac=0.15, cx_prob=0.9, mut_prob=0.9,
           patience=25, max_restarts=3, keep_frac_on_restart=0.25, sigma_decay=0.8, verbose=True):
    pop_size = len(pop)
    elite_k = max(1, int(pop_size * elite_frac))

    best = None
    best_score = -1e18
    best_total = 0.0
    best_pen = 0.0
    best_cov = None

    no_improve = 0
    restarts = 0
    # initial reseed sigmas
    rs_sigma_v, rs_sigma_deg, rs_sigma_r, rs_sigma_f = 4.0, 4.0, 0.4, 0.4

    for g in range(1, n_gen+1):
        scores = np.zeros(pop_size)
        totals = np.zeros(pop_size)
        pens = np.zeros(pop_size)
        # ---- evaluate ----
        for i, ind in enumerate(pop):
            v, th, r, f = ind
            fit, total, pen, cov = evaluate_plan(v, th, bomb_owner, r, f, t_grid, M, N_hat)
            scores[i] = fit; totals[i] = total; pens[i] = pen
        gen_best_idx = int(np.argmax(scores))
        gen_best_score = float(scores[gen_best_idx])
        gen_best_total = float(totals[gen_best_idx])
        gen_best_pen = float(pens[gen_best_idx])
        gen_best = (pop[gen_best_idx][0].copy(),
                    pop[gen_best_idx][1].copy(),
                    pop[gen_best_idx][2].copy(),
                    pop[gen_best_idx][3].copy())
        # update global best
        if gen_best_score > best_score + 1e-9:
            best_score = gen_best_score
            best_total = gen_best_total
            best_pen = gen_best_pen
            # recompute best_cov to keep memory low (or store from eval loop)
            _, _, _, best_cov = evaluate_plan(gen_best[0], gen_best[1], bomb_owner, gen_best[2], gen_best[3],
                                              t_grid, M, N_hat)
            best = gen_best
            no_improve = 0
        else:
            no_improve += 1

        if verbose:
            print(f"[GA] Gen {g:03d}: best_fit={gen_best_score:.2f}, mean_fit={scores.mean():.2f}, "
                  f"best_total={gen_best_total:.2f}, best_pen={gen_best_pen:.3f}, no_improve={no_improve}")

        # ---- stagnation-triggered partial restart ----
        if no_improve >= patience and restarts < max_restarts:
            keep_k = max(1, int(pop_size * keep_frac_on_restart))
            elite_idx = np.argsort(-scores)[:keep_k]
            elites = [ (pop[i][0].copy(), pop[i][1].copy(), pop[i][2].copy(), pop[i][3].copy()) for i in elite_idx ]
            pop = reseed_around_elites(elites, keep_k=keep_k, pop_size=pop_size, t_grid=t_grid,
                                       sigma_v=rs_sigma_v, sigma_deg=rs_sigma_deg,
                                       sigma_r=rs_sigma_r, sigma_f=rs_sigma_f)
            no_improve = 0
            restarts += 1
            # anneal sigmas
            rs_sigma_v *= sigma_decay
            rs_sigma_deg *= sigma_decay
            rs_sigma_r *= sigma_decay
            rs_sigma_f *= sigma_decay
            if verbose:
                print(f"[GA-RESTART] triggered at Gen {g}, keep {keep_k}/{pop_size} elites, "
                      f"new sigmas v={rs_sigma_v:.2f},deg={rs_sigma_deg:.2f},r={rs_sigma_r:.2f},f={rs_sigma_f:.2f} "
                      f"(restart #{restarts})")
            # go next generation
            continue

        # ---- standard GA step: elites + offspring ----
        elite_idx = np.argsort(-scores)[:elite_k]
        elites = [ (pop[i][0].copy(), pop[i][1].copy(), pop[i][2].copy(), pop[i][3].copy()) for i in elite_idx ]

        # roulette selection
        probs = scores - scores.min() + 1e-9
        probs = probs / probs.sum()
        def pick_parent():
            return pop[np.random.choice(pop_size, p=probs)]

        children = []
        while len(children) + len(elites) < pop_size:
            if np.random.rand() < cx_prob:
                c = uniform_crossover(pick_parent(), pick_parent())
            else:
                p = pick_parent()
                c = (p[0].copy(), p[1].copy(), p[2].copy(), p[3].copy())
            if np.random.rand() < mut_prob:
                c = mutate(c, t_grid)
            children.append(c)

        pop = elites + children

    return best, best_score, best_total, best_pen, best_cov

# =================== Main ===================
def main():
    # Build horizon
    T_end = compute_horizon(M0, MISSILE_SPEED)
    t_grid = np.arange(0.0, T_end + 1e-9, DT)
    M, N_hat = missile_trajectories(M0, t_grid)

    # Seed pop with your large defaults (adjust freely on your machine)
    global BOMB_OWNER
    BOMB_OWNER, pop = seed_initial_population(pop_size=150, t_grid=t_grid, with_speed=True, with_theta=True)

    # Run GA with stagnation restarts (defaults match your scale)
    best, best_fit, best_total, best_pen, best_cov = run_ga(
        pop, BOMB_OWNER, t_grid, M, N_hat,
        n_gen=500, elite_frac=0.20, cx_prob=0.9, mut_prob=0.9,
        patience=50, max_restarts=10, keep_frac_on_restart=0.25, sigma_decay=1.2, verbose=True
    )

    v_b, th_b, r_b, f_b = best
    print("\\n===== GA (Penalty + Restart) 最优解 =====")
    print(f"适应度 = 覆盖总时长 - {LAMBDA_GAP} * 缺口 = {best_fit:.2f}")
    print(f"覆盖总时长（去重统计）= {best_total:.2f} s")
    print(f"罚项（总缺口）= {best_pen:.3f} s -> 惩罚 = {LAMBDA_GAP*best_pen:.2f}")
    for i in range(N_DRONES):
        print(f"无人机#{i}: v={v_b[i]:.1f} m/s, θ={np.rad2deg(th_b[i]):.1f}°")
    by_drone = [[] for _ in range(N_DRONES)]
    for idx, d in enumerate(BOMB_OWNER):
        by_drone[d].append((r_b[idx], f_b[idx], r_b[idx]+f_b[idx]))
    for i in range(N_DRONES):
        by_drone[i].sort(key=lambda x: x[0])
        gaps = []
        for k in range(1, len(by_drone[i])):
            gaps.append(by_drone[i][k][0] - by_drone[i][k-1][0])
        print(f"  机#{i} gaps: {['%.2f'%g for g in gaps]}")
        for k,(rel,fuse,tau) in enumerate(by_drone[i],1):
            print(f"  机#{i} 弹{k}: 释放t={rel:.2f}s, 引信={fuse:.2f}s, 起爆t={tau:.2f}s")

    # Save results
    np.save('/mnt/data/ga_penalty_restart_blocked01.npy', best_cov.astype(int))
    np.save('/mnt/data/ga_penalty_restart_t_grid.npy', t_grid)
    np.save('/mnt/data/ga_penalty_restart_v.npy', v_b)
    np.save('/mnt/data/ga_penalty_restart_theta_deg.npy', np.rad2deg(th_b))
    np.save('/mnt/data/ga_penalty_restart_release.npy', r_b)
    np.save('/mnt/data/ga_penalty_restart_fuse.npy', f_b)
    print("\\n已保存：ga_penalty_restart_* 一组文件")

if __name__ == '__main__':
    main()
