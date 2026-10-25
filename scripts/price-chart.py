
#%%

import matplotlib.pyplot as plt

# 6-Year Historical Dataset
years = [ "2018/19", "2019/20", "2020/21",'2021/22', '2022/23', '2023/24', '2024/25', '2025/26', '2026/27', '2027/28\n(proposed)']
adult_payg =   [2.,   2.,   4.00, 4.05, 4.25, 4.45, 4.70, 4.80, 5.00, 7.5]
conc_payg =    [1.,   1.,   2.40, 2.43, 2.55, 2.65, 2.80, 2.90, 3.00, 3.75]
adult_season = [125., 125., 125., 125.00, 131.25, 137.80, 146.50, 150.50, 157.00, 360]
conc_season =  [66.,  66.,  66.,  75.97, 78.75, 82.65, 88.00, 90.00, 94.00, 180]

print(len(years))
print(len(adult_payg))
print(len(conc_payg))
print(len(adult_season))
print(len(conc_season))

fig, ax1 = plt.subplots(figsize=(10, 6))

# Primary Y-Axis configuration (PAYG Dips)
color_payg = '#1f77b4' # Muted Blue
ax1.set_xlabel('Financial Year', fontweight='bold', labelpad=12)
ax1.set_ylabel('PAYG Single Ticket Price (£)', color=color_payg, fontweight='bold', labelpad=8)
line1 = ax1.plot(years, adult_payg, marker='o', color=color_payg, linewidth=2.5, label='Adult PAYG (£)')
line2 = ax1.plot(years, conc_payg, marker='s', linestyle='--', color=color_payg, linewidth=2, label='Concession PAYG (£)')
ax1.tick_params(axis='y', labelcolor=color_payg)
ax1.set_ylim(0.0, 25.00)
ax1.grid(True, linestyle=':', alpha=0.6)

# Secondary Y-Axis configuration (12-Month Season Tickets)
ax2 = ax1.twinx()
color_season = '#d62728' # Muted Red
ax2.set_ylabel('12-Month Season Ticket Price (£)', color=color_season, fontweight='bold', labelpad=12)
line3 = ax2.plot(years, adult_season, marker='^', color=color_season, linewidth=2.5, label='Adult 12M Season (£)')
line4 = ax2.plot(years, conc_season, marker='v', linestyle='--', color=color_season, linewidth=2, label='Concession 12M Season (£)')
ax2.tick_params(axis='y', labelcolor=color_season)
ax2.set_ylim(0.0, 370.00)

# Label each line at its final point with an arrow.
ax1.annotate(
    f'Adult PAYG (£{adult_payg[-1]:.2f})',
    xy=(years[-1], adult_payg[-1]), xytext=(-12, -34),
    textcoords='offset points', ha='right', color=color_payg,
    arrowprops=dict(arrowstyle='->', color=color_payg),
)
ax1.annotate(
    f'Concession PAYG (£{conc_payg[-1]:.2f})',
    xy=(years[-1], conc_payg[-1]), xytext=(-12, -26),
    textcoords='offset points', ha='right', color=color_payg,
    arrowprops=dict(arrowstyle='->', color=color_payg),
)
ax2.annotate(
    f'Adult 12M Season (£{adult_season[-1]:.2f})',
    xy=(years[-1], adult_season[-1]), xytext=(-12, 35),
    textcoords='offset points', ha='right', color=color_season,
    arrowprops=dict(arrowstyle='->', color=color_season),
)
ax2.annotate(
    f'Concession 12M Season (£{conc_season[-1]:.2f})',
    xy=(years[-1], conc_season[-1]), xytext=(-12, 26),
    textcoords='offset points', ha='right', color=color_season,
    arrowprops=dict(arrowstyle='->', color=color_season),
)

# Consolidation of separate axis parameters into a single unified Legend box
all_lines = line1 + line2 + line3 + line4
all_labels = [l.get_label() for l in all_lines]
ax1.legend(all_lines, all_labels, loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e2e2')

plt.title('Hampstead Heath Bathing Ponds\n6-Year User Fee Trajectory (Dual Y-Axis)', fontweight='bold', fontsize=14, pad=15)
fig.tight_layout()

# Export chart out as png file
plt.savefig('bathing_ponds_fee_trajectory.png', dpi=300)
plt.show()

# %%
