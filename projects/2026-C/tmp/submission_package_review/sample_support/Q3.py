# Genetic algorithm to optimize 3-smoke deployment (Problem 3)
# The code simulates missile and drone motion, smoke grenade physics and cloud shielding,
# then runs a simple real-valued GA to maximize shielding time for missile M1.
# It saves the best parameters and the three explosion coordinates to files.
# Execution may take a little time depending on GA settings.

import numpy as np
import math
import json
import time
import os
import pandas as pd
from random import random, randrange, uniform, gauss, sample, randint

# ---------- Scenario constants ----------
M0 = np.array([20000.0, 0.0, 2000.0])   # missile initial pos
F0 = np.array([17800.0, 0.0, 1800.0])   # drone initial pos
target_center = np.array([0.0, 200.0, 5.0])  # true target centre (x,y,z)
v_missile = 300.0  # m/s

g = 9.8  # gravity
cloud_radius = 10.0  # m
cloud_descent_speed = 3.0  # m/s
cloud_effect_duration = 20.0  # seconds after explosion

# missile direction unit vector towards origin (fake target at origin)
fake_target = np.array([0.0, 0.0, 0.0])
missile_to_target_vec = fake_target - M0
missile_dist_to_fake = np.linalg.norm(missile_to_target_vec)
missile_dir = missile_to_target_vec / missile_dist_to_fake
t_impact = 12.5

# Time sampling resolution for shielding integration
dt = 0.01  # seconds (tradeoff between speed and accuracy)
time_grid = np.arange(0.0, t_impact + dt/2, dt)

# ---------- Helper kinematic functions ----------
def missile_pos(t):
    """Position of missile M1 at time t (starts at t=0)."""
    if t < 0: t = 0.0
    if t > t_impact: t = t_impact
    return M0 + missile_dir * v_missile * t

def drone_pos(t, theta, v):
    """Drone straight-line motion at fixed altitude z=1800.
       theta in radians from +x axis ccw.
    """
    vx = v * math.cos(theta)
    vy = v * math.sin(theta)
    return F0 + np.array([vx * t, vy * t, 0.0])

def grenade_explosion_position(t_rel, tau, theta, v):
    """Compute grenade explosion position (x,y,z) given release time t_rel and fuse tau.
       The grenade is released at drone_pos(t_rel) and undergoes horizontal motion with
       drone velocity and vertical free fall for duration tau = t_ex - t_rel.
       Returns (pos_explosion, t_explosion)
    """
    t_ex = t_rel + tau
    # horizontal movement during fuse time: v * dir * tau
    vx = v * math.cos(theta)
    vy = v * math.sin(theta)
    release_pos = drone_pos(t_rel, theta, v)  # includes z = 1800
    # position at explosion:
    x_ex = release_pos[0] + vx * tau
    y_ex = release_pos[1] + vy * tau
    z_ex = release_pos[2] - 0.5 * g * (tau ** 2)
    return np.array([x_ex, y_ex, z_ex]), t_ex

def cloud_center_at_time(pos_explosion, t_explosion, t):
    """Cloud center position at time t (t >= t_explosion)."""
    dt_after = t - t_explosion
    if dt_after < 0:
        return None
    z = pos_explosion[2] - cloud_descent_speed * dt_after
    return np.array([pos_explosion[0], pos_explosion[1], z])

def point_to_segment_distance(point, seg_a, seg_b, return_u_raw=False):
    AB = seg_b - seg_a
    AB2 = np.dot(AB, AB)
    if AB2 == 0.0:
        # 退化线段：A==B
        dist = np.linalg.norm(point - seg_a)
        return (dist, 0.0) if not return_u_raw else (dist, 0.0, 0.0)
    u_raw = np.dot(point - seg_a, AB) / AB2
    u_clamped = min(1.0, max(0.0, u_raw))
    closest = seg_a + u_clamped * AB
    dist = np.linalg.norm(point - closest)
    return (dist, u_clamped) if not return_u_raw else (dist, u_clamped, u_raw)

# ---------- Shielding indicator ----------
def is_shielded_at_time(t, explosions):
    """Determine if missile is shielded at time t by any cloud.
       explosions: list of dicts with keys pos_ex (3), t_ex (scalar).
    """
    # missile position and target center form segment
    if t < 0 or t > t_impact:
        return False
    Mpos = missile_pos(t)
    Tpos = target_center
    # check each cloud if active at time t
    for ex in explosions:
        t_ex = ex['t_ex']
        if t < t_ex or t > t_ex + cloud_effect_duration:
            continue  # cloud not yet formed or already dissipated
        
        if not (ex['t_ex'] <= t <= ex['t_end']):
            continue
        S = cloud_center_at_time(ex['pos_ex'], ex['t_ex'], t)
        if S is None or S[2] <= 0.0:   # 双保险
            continue
        
        # geometric check: distance from cloud center to missile-target segment, and between endpoints
        dist, u = point_to_segment_distance(S, Mpos, Tpos)
        # require cloud center projection between missile and target (0<=u<=1) AND distance<=radius
        dist, u_clamped, u_raw = point_to_segment_distance(S, Mpos, Tpos, return_u_raw=True)
        # 仅当投影在段上（允许端点，给一点点容差）且距离 <= 半径 才算遮蔽
        if (-1e-12 <= u_raw <= 1.0 + 1e-12) and (dist <= cloud_radius):
            return True
    return False

# ---------- Fitness evaluation ----------
def evaluate_solution(chromosome, return_explosions=False):
    """Chromosome structure:
       [theta (rad), v (m/s), t_rel1, t_rel2, t_rel3, tau1, tau2, tau3]
    """
    theta, v = chromosome[0], chromosome[1]
    t_rel = chromosome[2:5]
    taus = chromosome[5:8]
    # validity checks and penalties:
    # enforce bounds:
    if not (math.pi/2 <= theta <= math.pi):
        return 0.0 if not return_explosions else (0.0, [])
    if not (70.0 <= v <= 140.0):
        return 0.0 if not return_explosions else (0.0, [])
    # times within [0, t_impact]
    if np.any(np.array(t_rel) < 0.0) or np.any(np.array(t_rel) > t_impact):
        return 0.0 if not return_explosions else (0.0, [])
    if np.any(np.array(taus) < 0.0) or np.any(np.array(taus) > cloud_effect_duration):
        return 0.0 if not return_explosions else (0.0, [])
    # order constraint and >1s separation
    if not (t_rel[0] < t_rel[1] < t_rel[2]):
        # heavy penalty
        return 0.0 if not return_explosions else (0.0, [])
    if not ( (t_rel[1]-t_rel[0] > 1.0) and (t_rel[2]-t_rel[1] > 1.0) ):
        return 0.0 if not return_explosions else (0.0, [])
    # explosions must occur before impact (otherwise useless)
    t_ex = [t_rel[i] + taus[i] for i in range(3)]
    if any(te > t_impact for te in t_ex):
        return 0.0 if not return_explosions else (0.0, [])
    # compute explosion positions
    explosions = []
    for i in range(3):
        pos_ex, t_e = grenade_explosion_position(t_rel[i], taus[i], theta, v)
    # 若起爆点已在地面/地下，则直接判为无效（可按需给 0 分）
        if pos_ex[2] <= 0.0:
            return 0.0 if not return_explosions else (0.0, [])
        t_end = min(t_impact, t_e + cloud_effect_duration, t_e + pos_ex[2] / cloud_descent_speed)
        explosions.append({'pos_ex': pos_ex, 't_ex': t_e, 't_end': t_end})
    # Now integrate shielding indicator over time grid (from earliest explosion to missile impact)
    earliest_ex = min([ex['t_ex'] for ex in explosions])
    # start integration from earliest_ex (clouds before that do not exist)
    idx_start = int(max(0, math.floor((earliest_ex) / dt)))
    total = 0.0
    for ti in range(idx_start, len(time_grid)):
        t = time_grid[ti]
        if t > t_impact:
            break
        if is_shielded_at_time(t, explosions):
            total += dt
    if return_explosions:
        return total, explosions
    return total

# ---------- Simple real-valued GA implementation ----------
def initialize_population(pop_size):
    pop = []
    for _ in range(pop_size):
        theta = uniform(math.pi/2, math.pi)
        v = uniform(70.0, 140.0)
        # sample three release times uniformly and sort; ensure separation >1 by resampling if needed
        # to avoid bias, we'll try a few attempts then accept (invalids penalized)
        t_rel = sorted([uniform(0.0, max(0.0, t_impact-1.0)) for _ in range(3)])
        taus = [uniform(0.0, min(cloud_effect_duration, t_impact - t_rel[i])) for i in range(3)]
        chrom = np.array([theta, v, t_rel[0], t_rel[1], t_rel[2], taus[0], taus[1], taus[2]])
        pop.append(chrom)
    return pop

def tournament_selection(pop, fitnesses, k=3):
    n = len(pop)
    best = None; best_f = -1e9
    for _ in range(k):
        i = randint(0, n-1)
        if fitnesses[i] > best_f or best is None:
            best = pop[i]; best_f = fitnesses[i]
    return best.copy()

def crossover(parent1, parent2, alpha=0.5):
    # blend crossover for real-valued genes (BLX-like)
    child1 = parent1.copy()
    child2 = parent2.copy()
    for i in range(len(parent1)):
        if random() < 0.7:
            gamma = uniform(-alpha, 1+alpha)
            c1 = gamma*parent1[i] + (1-gamma)*parent2[i]
            c2 = (1-gamma)*parent1[i] + gamma*parent2[i]
            child1[i] = c1
            child2[i] = c2
    return child1, child2

def mutate(chrom, sigma=0.1):
    child = chrom.copy()
    for i in range(len(child)):
        if random() < 0.2:
            if i == 0:  # theta
                child[i] += gauss(0, sigma*(math.pi/4))
            elif i == 1:  # v
                child[i] += gauss(0, sigma*20)
            else:
                child[i] += gauss(0, sigma*5)
    # clamp bounds for theta and v and times
    child[0] = max(math.pi/2, min(math.pi, child[0]))
    child[1] = max(70.0, min(140.0, child[1]))
    for j in range(2,5):
        child[j] = max(0.0, min(t_impact, child[j]))
    for j in range(5,8):
        child[j] = max(0.0, min(cloud_effect_duration, child[j]))
    return child

# ---------- Run GA ----------
pop_size = 60
generations = 150
elitism = 2

np.random.seed(42)
pop = initialize_population(pop_size)

# evaluate initial fitnesses
fitnesses = [evaluate_solution(ind) for ind in pop]
best_idx = int(np.argmax(fitnesses))
best = pop[best_idx].copy()
best_score = fitnesses[best_idx]
start_time = time.time()

for gen in range(generations):
    new_pop = []
    # elitism: carry over top individuals
    sorted_idx = sorted(range(len(pop)), key=lambda i: fitnesses[i], reverse=True)
    for i in range(elitism):
        new_pop.append(pop[sorted_idx[i]].copy())
    # produce offspring
    while len(new_pop) < pop_size:
        p1 = tournament_selection(pop, fitnesses, k=3)
        p2 = tournament_selection(pop, fitnesses, k=3)
        c1, c2 = crossover(p1, p2, alpha=0.5)
        c1 = mutate(c1, sigma=0.2)
        c2 = mutate(c2, sigma=0.2)
        new_pop.append(c1)
        if len(new_pop) < pop_size:
            new_pop.append(c2)
    pop = new_pop
    fitnesses = [evaluate_solution(ind) for ind in pop]
    cur_best_idx = int(np.argmax(fitnesses))
    cur_best_score = fitnesses[cur_best_idx]
    if cur_best_score > best_score:
        best_score = cur_best_score
        best = pop[cur_best_idx].copy()
    # optional: print progress
    if gen % 5 == 0 or gen == generations-1:
        print(f"Gen {gen:3d}: best_score = {best_score:.3f} s")

end_time = time.time()
print(f"GA finished in {end_time - start_time:.1f} seconds. Best shielding time = {best_score:.3f} s")

# ---------- Compute explosion coordinates for best solution ----------
best_total, best_explosions = evaluate_solution(best, return_explosions=True)

expl_coords = [ex['pos_ex'].tolist() for ex in best_explosions]
expl_times = [ex['t_ex'] for ex in best_explosions]

# Save results to files
out_dir = 'results/3smoke_results'
os.makedirs(out_dir, exist_ok=True)
params = {
    'theta_rad': float(best[0]),
    'theta_deg': float(best[0]*180.0/math.pi),
    'v': float(best[1]),
    't_rel_1': float(best[2]),
    't_rel_2': float(best[3]),
    't_rel_3': float(best[4]),
    'tau_1': float(best[5]),
    'tau_2': float(best[6]),
    'tau_3': float(best[7]),
    't_ex_1': float(expl_times[0]),
    't_ex_2': float(expl_times[1]),
    't_ex_3': float(expl_times[2]),
    'shielding_time_s': float(best_total)
}
with open(os.path.join(out_dir, 'best_parameters.json'), 'w') as f:
    json.dump(params, f, indent=2)

# save explosion coordinates
df_ex = pd.DataFrame({
    'explosion_index': [1,2,3],
    't_ex': expl_times,
    'x_ex': [c[0] for c in expl_coords],
    'y_ex': [c[1] for c in expl_coords],
    'z_ex': [c[2] for c in expl_coords]
})
df_ex.to_csv(os.path.join(out_dir, 'explosion_coordinates.csv'), index=False)
with open(os.path.join(out_dir, 'explosion_coordinates.json'), 'w') as f:
    json.dump({'explosions': [
        {'index': i+1, 't_ex': expl_times[i], 'pos_ex': expl_coords[i]} for i in range(3)
    ]}, f, indent=2)

print("\n========= 最佳参数结果 =========")
print(f"最优方位角 θ: {params['theta_deg']:.3f}°")
print(f"最优速度 v: {params['v']:.3f} m/s")
print(f"第1枚弹释放时间 t_rel_1: {params['t_rel_1']:.3f} s")
print(f"第2枚弹释放时间 t_rel_2: {params['t_rel_2']:.3f} s")
print(f"第3枚弹释放时间 t_rel_3: {params['t_rel_3']:.3f} s")
print(f"第1枚弹起爆延迟 τ1: {params['tau_1']:.3f} s")
print(f"第2枚弹起爆延迟 τ2: {params['tau_2']:.3f} s")
print(f"第3枚弹起爆延迟 τ3: {params['tau_3']:.3f} s")
print(f"第1枚弹起爆时间 t_ex_1: {params['t_ex_1']:.3f} s")
print(f"第2枚弹起爆时间 t_ex_2: {params['t_ex_2']:.3f} s")
print(f"第3枚弹起爆时间 t_ex_3: {params['t_ex_3']:.3f} s")
print(f"最大遮蔽时间: {params['shielding_time_s']:.3f} s")
print("\n三枚弹起爆坐标：")
for i, coord in enumerate(expl_coords, 1):
    print(f"第{i}枚弹: x={coord[0]:.2f}, y={coord[1]:.2f}, z={coord[2]:.2f}")

# save best chromosome and score
np.savez(os.path.join(out_dir, 'best_solution.npz'), best=best, score=best_score, params=params)

# present results to user
results_df = pd.DataFrame([params])
display_df = pd.concat([results_df, df_ex.set_index(df_ex.columns[0]).T.reset_index().T], axis=1)
# Use pandas display for neat output

print("\nSaved files:")
print(os.path.join(out_dir, 'best_parameters.json'))
print(os.path.join(out_dir, 'best_solution.npz'))
print(os.path.join(out_dir, 'explosion_coordinates.csv'))

# Return summary dict for chat
{
    "best_score_s": float(best_score),
    "best_parameters": params,
    "explosion_coordinates": expl_coords,
    "saved_files": {
        "best_parameters_json": os.path.join(out_dir, 'best_parameters.json'),
        "best_solution_npz": os.path.join(out_dir, 'best_solution.npz'),
        "explosion_coordinates_csv": os.path.join(out_dir, 'explosion_coordinates.csv'),
        "explosion_coordinates_json": os.path.join(out_dir, 'explosion_coordinates.json')
    }
}
