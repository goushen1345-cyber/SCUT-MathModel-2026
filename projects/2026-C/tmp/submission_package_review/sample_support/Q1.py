
import numpy as np
import matplotlib.pyplot as plt

# Constants
g = 9.8  # m/s²
true_target = np.array([0, 200, 5])  # True target point

# Missile M1 initial position and velocity
Pm0 = np.array([20000, 0, 2000])
dm = np.linalg.norm(Pm0)
um = -Pm0 / dm
Vm = 300 * um  # Velocity vector

# Calculate missile arrival time to fake target (0,0,0)
t_arrival = dm / 300
print(f"Missile hits the fake target at: {t_arrival:.2f} s")
# v=76.47 m/s, θ=172.43°, t_rel=0.00 s, fuse=2.36 s
# Drone FY1 initial position and velocity
Pd0 = np.array([17800, 0, 1800])

vd = 120  # m/s
theta = np.pi  # Towards fake target, negative x
ud = np.array([np.cos(theta), np.sin(theta), 0])  # (-1, 0, 0)
Vd = vd * ud  # (-120, 0, 0)

# Times
t_drop = 1.5  # s after task

delta_t = 3.6  # s after drop to explode
t_expl = t_drop + delta_t

# Drop point
P_drop = Pd0 + Vd * t_drop

# Explode point
dt = delta_t
P_expl = P_drop + Vd * dt - np.array([0, 0, 0.5 * g * dt**2])

# Function to compute distance from point Pc to line Pm to Pt
def dist_to_line(Pm, Pt, Pc):
    vec_mt = Pt - Pm
    vec_mc = Pc - Pm
    cross = np.cross(vec_mc, vec_mt)
    d = np.linalg.norm(cross) / np.linalg.norm(vec_mt)
    return d

# Function to check if Pc is between Pm and Pt
def is_between(Pm, Pt, Pc):
    vec_mt = Pt - Pm
    vec_mc = Pc - Pm
    # Scalar projection of vec_mc onto vec_mt
    norm_mt = np.linalg.norm(vec_mt)
    if norm_mt == 0:
        return False
    s = np.dot(vec_mc, vec_mt) / (norm_mt ** 2)
    # Check if projection lies within the segment
    return 0 < s < 1

# Simulate time from t_expl to min(t_expl + 20, t_arrival), step 0.01 s
dt_sim = 0.001
t_sim = np.arange(t_expl, min(t_expl + 20, t_arrival) + dt_sim, dt_sim)
distances = []
shield_times = []

for t in t_sim:
    # Missile position
    Pm_t = Pm0 + Vm * t
    
    # Cloud center
    tau = t - t_expl
    Pc_t = P_expl - np.array([0, 0, 3 * tau])
    
    # Distance to sightline
    d_t = dist_to_line(Pm_t, true_target, Pc_t)
    distances.append(d_t)
    
    # Check if cloud is between missile and target
    if d_t <= 10 and is_between(Pm_t, true_target, Pc_t):
        shield_times.append(t)

# Effective shield duration
if shield_times:
    shield_duration = max(shield_times) - min(shield_times) + dt_sim
else:
    shield_duration = 0

print(f"Effective shielding duration: {shield_duration:.4f} s")

# Plotting the distance d vs time t
plt.figure(figsize=(10, 6))
plt.plot(t_sim, distances, label='Distance to sightline (m)')
plt.axhline(y=10, color='r', linestyle='--', label='Shielding threshold (10 m)')
plt.axvline(x=t_expl, color='g', linestyle='--', label='Explosion time')
plt.axvline(x=min(t_expl + 20, t_arrival), color='b', linestyle='--', label='Shielding end time')
plt.xlabel('Time (s)')
plt.ylabel('Distance (m)')
plt.title('Distance from Cloud Center to Missile-Target Sightline vs Time')
plt.legend()
plt.grid(True)
plt.show()
