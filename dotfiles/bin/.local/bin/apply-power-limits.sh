#!/usr/bin/env bash
set -e

# 1. Set max battery charge threshold to 80%
if [ -f /sys/class/power_supply/BAT0/charge_control_end_threshold ]; then
    echo 80 > /sys/class/power_supply/BAT0/charge_control_end_threshold
    echo "[OK] Battery charge limit set to: $(cat /sys/class/power_supply/BAT0/charge_control_end_threshold)%"
fi

# 2. Disable CPU boost
if [ -f /sys/devices/system/cpu/cpufreq/boost ]; then
    echo 0 > /sys/devices/system/cpu/cpufreq/boost
    echo "[OK] CPU Boost disabled: boost=$(cat /sys/devices/system/cpu/cpufreq/boost)"
fi

# 3. Cap CPU max frequency to 1.7 GHz (1700000 kHz)
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    if [ -f "$policy/scaling_max_freq" ]; then
        echo 1700000 > "$policy/scaling_max_freq"
    fi
done
echo "[OK] CPU frequency capped to: $(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq) kHz (1.7 GHz)"

modprobe cpufreq_powersave 2>/dev/null || true
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
  if grep -q "powersave" "$policy/scaling_available_governors" 2>/dev/null; then
    echo powersave > "$policy/scaling_governor"
  fi
done

