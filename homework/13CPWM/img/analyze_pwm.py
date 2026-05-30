import csv

times, ch0, ch1 = [], [], []
with open('d:/Github/Embedded-System-Design/homework/13CPWM/img/2026-05-28_16-54-03.csv', 'r', encoding='iso-8859-1') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        times.append(float(row[0]))
        ch0.append(int(row[1]))
        ch1.append(int(row[2]))

print(f'Total data points: {len(times)}')
print(f'Duration: {times[-1] - times[0]:.6f} s')

# Ch1 rising edges = period start
ch1_rising = [times[i] for i in range(1, len(times)) if ch1[i-1] == 0 and ch1[i] == 1]
periods = [ch1_rising[i+1] - ch1_rising[i] for i in range(len(ch1_rising)-1)]
avg_period = sum(periods) / len(periods) * 1e6
print(f'\n=== Period & Frequency ===')
print(f'Cycles: {len(periods)}')
print(f'Period (first 5): {[round(p*1e6,2) for p in periods[:5]]} us')
print(f'Period (last 5):  {[round(p*1e6,2) for p in periods[-5:]]} us')
print(f'Average period: {avg_period:.4f} us')
print(f'Frequency: {1/(avg_period/1e6)/1000:.2f} kHz')

# Dead time analysis
dead_times = []
for i in range(1, len(times)):
    prev = (ch0[i-1] == 0 and ch1[i-1] == 0)
    curr = (ch0[i] == 0 and ch1[i] == 0)
    if not prev and curr:
        ds = times[i]
    elif prev and not curr:
        dead_times.append(times[i] - ds)

avg_dead = sum(dead_times) / len(dead_times) * 1e9
print(f'\n=== Dead Time ===')
print(f'Intervals: {len(dead_times)} (2 per cycle)')
print(f'Dead time (first 10): {[round(d*1e9) for d in dead_times[:10]]} ns')
print(f'Average: {avg_dead:.1f} ns')
print(f'Min: {min(dead_times)*1e9:.1f} ns')
print(f'Max: {max(dead_times)*1e9:.1f} ns')

# Duty cycle
c0_on, c1_on = [], []
s0 = s1 = 0
for i in range(1, len(times)):
    if ch0[i-1] == 0 and ch0[i] == 1:
        s0 = times[i]
    elif ch0[i-1] == 1 and ch0[i] == 0:
        c0_on.append(times[i] - s0)
    if ch1[i-1] == 0 and ch1[i] == 1:
        s1 = times[i]
    elif ch1[i-1] == 1 and ch1[i] == 0:
        c1_on.append(times[i] - s1)

avg_c0 = sum(c0_on) / len(c0_on) * 1e6
avg_c1 = sum(c1_on) / len(c1_on) * 1e6
print(f'\n=== Duty Cycle ===')
print(f'Ch0 ON time: {avg_c0:.4f} us ({avg_c0/avg_period*100:.1f}%)')
print(f'Ch1 ON time: {avg_c1:.4f} us ({avg_c1/avg_period*100:.1f}%)')
print(f'Sum check: {avg_c0 + avg_c1 + avg_dead/1000*2:.4f} us (should = {avg_period:.4f} us)')

# Print first 3 cycles detail
print(f'\n=== First 3 Cycles Detail ===')
states = []
prev_s = None
for i in range(len(times)):
    s = (ch0[i], ch1[i])
    if s != prev_s:
        states.append((times[i], ch0[i], ch1[i]))
        prev_s = s
    if len(states) >= 30:
        break
for t, c0, c1 in states:
    print(f'  {t*1e6:9.4f} us  Ch0={c0}  Ch1={c1}')
