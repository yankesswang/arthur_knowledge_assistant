# LLM Server 突然關機硬體排查指引

日期：2026-05-19

## 目標

這份指引用來排查「LM Studio / 本機 LLM 推論時，整台電腦突然關機或重開」。

核心目標不是一次猜出壞哪個零件，而是用可重複測試把問題縮小到：

- RAM / XMP / 記憶體控制器
- GPU / 12VHPWR 線材 / PSU 瞬間功耗
- CPU / BIOS / 電壓與功耗限制
- 散熱 / 主機板保護
- 軟體服務混亂或 LLM server 本身 crash

## 目前這台機器的已知狀態

硬體與系統：

- CPU：Intel Core i9-14900K
- GPU：NVIDIA GeForce RTX 4090
- 主機板：Gigabyte Z690 AORUS MASTER
- BIOS：T0d，日期 2025-03-17
- RAM：系統可見約 62GiB
- PSU：1000W
- OS：Ubuntu 22.04，kernel 6.5.0-45-generic

已觀察到的現象：

- `last -x` 顯示多次 session 以 `crash` 結束。
- crash 前後的 journal 沒看到明確的 kernel panic、OOM killer、NVIDIA Xid、MCE、ECC、EDAC error。
- 多次 log 是直接中斷，這比較像整機斷電、主機板保護、PSU OCP/OPP、VRM/CPU/GPU 保護，而不是一般 app crash。

目前已做過的測試：

- 線上 RAM quickcheck：
  - 16GiB 通過
  - 32GiB 通過
- `/proc/meminfo`：`HardwareCorrupted: 0 kB`
- LM Studio `gpt-oss-20b` 壓測：
  - concurrency 1，660 秒，143 個 request，0 error
  - concurrency 4，660 秒，225 個 request，0 error
- concurrency 4 壓測峰值：
  - GPU 最高溫：71 C
  - GPU 最高功耗：約 309 W
  - GPU 最高 VRAM：約 19.7 GiB
  - GPU 最高利用率：95%
- 測試期間 kernel log 沒新增 `MCE/ECC/OOM/NVRM/Xid/panic/thermal` 相關錯誤。

重要限制：

- 目前 LM Studio 測試只把 RTX 4090 推到約 300W，還沒碰到 450W power limit。
- 1000W PSU 理論上足夠，但仍可能因線材、轉接頭、PSU 年齡、ATX 2.x 瞬間負載能力、UPS/延長線、主機板供電而觸發保護。
- 線上 RAM quickcheck 不能取代離線 MemTest86 / memtest86+。

## 判斷原則

### 1. 有 log 的 crash，多半偏軟體或 driver

如果 crash 前有這些 log，方向會比較明確：

- `Out of memory`
- `Killed process`
- `NVRM: Xid`
- `GPU has fallen off the bus`
- `Machine Check Exception`
- `Hardware Error`
- `thermal throttling`
- `kernel panic`

查詢：

```bash
journalctl -k -b -1 --no-pager -g 'mce|machine check|hardware error|edac|ecc|memory error|oom|out of memory|thermal|temperature|critical|watchdog|panic|segfault|nvrm|xid|pcie|aer'
```

### 2. log 直接中斷，多半偏硬體保護或斷電

如果前一個 boot 的尾端沒有正常 shutdown，也沒有 panic/OOM/Xid，下一個 boot 直接開始，優先懷疑：

- PSU 瞬間過載或保護
- RTX 4090 供電線材或 12VHPWR 接觸問題
- CPU/主機板 VRM 保護
- RAM/XMP 不穩造成硬重啟
- BIOS/CPU 微碼與電壓設定不穩
- AC 電源、UPS、延長線、插座問題

查詢：

```bash
journalctl --list-boots --no-pager
last -x -n 30
journalctl -b -1 -n 120 --no-pager
```

## 優先排查順序

### Step 0：先排除干擾服務

如果目前只用 LM Studio，不用 Ollama，先停掉 Ollama，避免搶 port、吃資源、洗 log。

```bash
sudo systemctl disable --now ollama.service
sudo systemctl disable --now snap.ollama.listener.service
```

確認：

```bash
systemctl status ollama.service snap.ollama.listener.service --no-pager
ss -ltnp 'sport = :11434'
```

預期：

- Ollama 不應該再 active。
- LM Studio 預設 server 是 `0.0.0.0:1234` 或 `127.0.0.1:1234`。

### Step 1：建立 baseline log

每次測試前記錄：

```bash
date
uptime -s
free -h
swapon --show
nvidia-smi --query-gpu=name,temperature.gpu,power.draw,power.limit,memory.used,memory.total,utilization.gpu,pstate --format=csv,noheader,nounits
sensors
```

記錄 CPU power limit：

```bash
cat /sys/devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_0_name
cat /sys/devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw
cat /sys/devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_1_name
cat /sys/devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_1_power_limit_uw
cat /sys/devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_2_name
cat /sys/devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_2_power_limit_uw
```

目前讀到的值：

- long_term：253W
- short_term：253W
- peak_power：380W

### Step 2：跑 LM Studio 可重複壓測

腳本位置：

```bash
scripts/lmstudio_crash_test.py
```

一般測試：

```bash
python3 scripts/lmstudio_crash_test.py \
  --duration 660 \
  --concurrency 1 \
  --max-tokens 1024 \
  --prompt-chars 8000 \
  --request-timeout 600 \
  --model gpt-oss-20b
```

併發測試：

```bash
python3 scripts/lmstudio_crash_test.py \
  --duration 660 \
  --concurrency 4 \
  --max-tokens 1024 \
  --prompt-chars 8000 \
  --request-timeout 900 \
  --model gpt-oss-20b
```

log 位置：

```text
logs/lmstudio-crash-test/<timestamp>/
```

看最後狀態：

```bash
tail -n 20 logs/lmstudio-crash-test/<timestamp>/events.jsonl
tail -n 20 logs/lmstudio-crash-test/<timestamp>/requests.jsonl
tail -n 20 logs/lmstudio-crash-test/<timestamp>/telemetry.csv
```

統計峰值：

```bash
awk -F, 'NR>1 {if ($10+0>maxt) maxt=$10+0; if ($11+0>maxp) maxp=$11+0; if ($13+0>maxm) maxm=$13+0; if ($15+0>maxu) maxu=$15+0} END {print "max_gpu_temp_c=" maxt; print "max_gpu_power_w=" maxp; print "max_gpu_mem_mib=" maxm; print "max_gpu_util_pct=" maxu}' logs/lmstudio-crash-test/<timestamp>/telemetry.csv
```

### Step 3：RAM / XMP 排查

目前線上 quickcheck 通過，但完整 RAM 排查仍要做離線測試。

建議流程：

1. 進 BIOS 關閉 XMP，使用 JEDEC 預設。
2. 用同一個 LM Studio 測試重跑。
3. 用 UEFI 版 MemTest86 或支援 UEFI 的 memtest86+ USB 開機。
4. 跑至少 4 passes；若要保守，跑過夜。
5. 如果有錯誤：
   - 單條 RAM 測
   - 換插槽測
   - 關閉 XMP 測
   - 降頻測

判讀：

- 關 XMP 後不再關機：高度懷疑 RAM/XMP/IMC 不穩。
- MemTest 有 error：RAM、插槽、IMC、XMP 設定其中之一有問題。
- MemTest 過夜通過但 LLM 仍重啟：往 GPU/PSU/CPU/主機板方向查。

### Step 4：GPU / PSU / 線材排查

RTX 4090 power limit 目前是 450W。

查詢：

```bash
nvidia-smi --query-gpu=name,power.draw,power.limit,power.default_limit,power.min_limit,power.max_limit --format=csv,noheader,nounits
```

隔離測試：先把 GPU 降到 350W。

```bash
sudo nvidia-smi -pl 350
```

重跑 LM Studio 測試。

恢復：

```bash
sudo nvidia-smi -pl 450
```

判讀：

- 350W 穩、450W 會關機：高度懷疑 PSU 瞬間負載、GPU 供電線、12VHPWR 接觸、PSU OCP/OPP。
- 350W 也會關機：不只 GPU 峰值，繼續查 RAM/CPU/主機板/AC 電源。
- 450W 壓測也穩：PSU/GPU 不是完全排除，但優先度降低。

硬體檢查：

- 確認 PSU 型號、年齡、是否 ATX 3.0/3.1。
- 4090 優先用 PSU 原生 12VHPWR / 12V-2x6 線。
- 如果用 4x8pin 轉接，確認每條 8pin 都是獨立線，不要 daisy-chain。
- 12VHPWR 插頭必須完全插到底，線不要在插頭根部急彎。
- 不要先接 UPS 或品質不明延長線；測試時直接接牆上插座或確認 UPS 額定足夠。
- 如果有另一顆高品質 1000W/1200W ATX 3.x PSU，交叉測試最有效。

### Step 5：CPU / BIOS / 主機板穩定性

i9-14900K 對 BIOS、電壓、功耗限制敏感。這台目前 PL1/PL2 是 253W，peak 380W。

建議：

1. BIOS 先載入 Optimized Defaults。
2. 關閉自動超頻、多核心增強、過度 aggressive 的電壓最佳化。
3. 使用 Intel default / baseline profile，如果 BIOS 有提供。
4. 保持 PL1/PL2 253W，不要解除功耗限制。
5. 如果曾經手動 undervolt / overclock，先全部恢復預設。
6. 到 Gigabyte 主機板支援頁確認 BIOS 是否有更新；更新前先備份設定並閱讀 release note。

判讀：

- BIOS default 後穩定：原先 BIOS/超頻/電壓設定不穩。
- CPU 壓測會直接重啟：CPU/VRM/散熱/BIOS 方向優先。
- 只有 GPU + CPU 同時負載會重啟：PSU 或主機板供電方向優先。

### Step 6：散熱檢查

查目前溫度：

```bash
sensors
nvidia-smi --query-gpu=temperature.gpu,temperature.memory,power.draw,utilization.gpu --format=csv
```

目前 LM Studio 測試 GPU 最高 71 C，並沒有熱保護跡象。

仍需檢查：

- CPU package 是否接近 100 C。
- GPU hotspot / memory junction 是否過高；一般 `nvidia-smi` 不一定讀得到完整欄位。
- 機殼風道、冷排、灰塵、風扇曲線。
- VRM 區域是否過熱；Linux 不一定能讀到主機板 VRM sensor。

判讀：

- 有 thermal throttling / critical shutdown log：散熱優先。
- 沒有 thermal log，但整機瞬斷：散熱不是第一嫌疑，但 VRM/PSU 保護仍可能無 log。

## 測試矩陣

每次只改一個變數。

| 測試 | GPU PL | XMP | CPU 設定 | LM Studio | 目標 |
|---|---:|---|---|---|---|
| A baseline | 450W | 原設定 | 原設定 | concurrency 1 | 確認基本穩定 |
| B 併發 | 450W | 原設定 | 原設定 | concurrency 4 | 測 server 併發 |
| C GPU 降功耗 | 350W | 原設定 | 原設定 | 同問題場景 | 判斷 PSU/GPU 瞬間負載 |
| D RAM 預設 | 450W | off | 原設定 | 同問題場景 | 判斷 XMP/RAM |
| E CPU baseline | 450W | off | Intel default | 同問題場景 | 判斷 CPU/BIOS |
| F 高壓重現 | 450W | 穩定設定 | 穩定設定 | 原本會關機的模型/參數 | 確認修復 |

每輪記錄：

- 開始時間、結束時間
- 是否重啟
- GPU max temp / power / VRAM / util
- request 成功/失敗數
- kernel log 是否有錯誤
- 是否有 Xid / MCE / OOM / thermal

## 如果再次突然關機，重開後第一時間收集

先不要重新跑模型，先收 log：

```bash
date
uptime -s
journalctl --list-boots --no-pager
last -x -n 30
journalctl -b -1 -n 200 --no-pager
journalctl -k -b -1 --no-pager -g 'mce|machine check|hardware error|edac|ecc|memory error|oom|out of memory|thermal|temperature|critical|watchdog|panic|segfault|nvrm|xid|pcie|aer'
```

### 已加上的持續硬體 log

2026-05-20 已完成：

- 新增 durable logger：`scripts/hardware_event_logger.py`
- 新增 user systemd unit 模板：`systemd/user/hardware-event-logger.service`
- 已複製並啟用到：`/home/trx50/.config/systemd/user/hardware-event-logger.service`
- 已執行：

```bash
systemctl --user daemon-reload
systemctl --user enable hardware-event-logger.service
systemctl --user restart hardware-event-logger.service
```

目前確認狀態：

- `hardware-event-logger.service` 是 `active (running)`。
- 主程序類似：`/usr/bin/python3 /home/trx50/Project/arthur_knowledge_assistant/scripts/hardware_event_logger.py --output-root /home/trx50/Project/arthur_knowledge_assistant/logs/hardware-event-log --interval 5 --detail-interval 60`
- `logs/hardware-event-log/latest` 會指向目前正在寫的 run。
- `logs/hardware-event-log/previous` 會指向上一個 run，方便重啟後查看重啟前最後資料。

目前已啟用 user-level service：

```bash
systemctl --user status hardware-event-logger.service --no-pager
```

它會每 5 秒把關鍵 telemetry durable 寫入：

```text
logs/hardware-event-log/latest/telemetry.csv
logs/hardware-event-log/latest/events.jsonl
```

紀錄內容包含：

- CPU package / core 溫度
- GPU 溫度、功耗、power limit、VRAM、utilization、clock、pstate
- RAM / swap / load
- LM Studio `127.0.0.1:1234/v1/models` 是否可回應
- 每分鐘的 LLM/Docker 相關 process snapshot
- 每分鐘的 kernel 關鍵錯誤掃描

實作細節：

- `telemetry.csv` 每 5 秒寫一筆，寫完立即 flush + `fsync`。
- `events.jsonl` 在啟動時記錄 baseline，之後每 60 秒寫 process snapshot、kernel 關鍵錯誤掃描、NVIDIA compute apps。
- 啟動時會記錄 `date`、`uptime -s`、`uname -a`、`/proc/cmdline`、`nvidia-smi -q -d POWER,TEMPERATURE,PERFORMANCE,CLOCK,MEMORY`。
- `latest` / `previous` symlink 會在每次 logger 啟動時更新。

如果再次硬重啟，重開後先看上一個 run 目錄最後幾筆：

```bash
readlink -f logs/hardware-event-log/latest
readlink -f logs/hardware-event-log/previous
tail -n 30 logs/hardware-event-log/latest/telemetry.csv
tail -n 80 logs/hardware-event-log/latest/events.jsonl
```

如果 logger 已經在重開後自動開始新的 run，真正要看的通常是：

```bash
tail -n 30 logs/hardware-event-log/previous/telemetry.csv
tail -n 80 logs/hardware-event-log/previous/events.jsonl
```

重點看重啟前最後 5-30 秒：

- `gpu_power_w` 是否接近 400W+ 或 power sample 是否接近 450W。
- `gpu_temp_c` 是否接近 80-90 C。
- `cpu_package_temp_c` / `cpu_max_core_temp_c` 是否接近 100 C。
- `mem_available_mib` 是否急速下降，`swap_used_mib` 是否明顯上升。
- `lmstudio_http_ok` 是否先變 0；如果只有它變 0 但系統沒重啟，是服務問題。
- `events.jsonl` 是否有 `NVRM/Xid/MCE/OOM/thermal/panic`。

限制：

- 這是 user service，現在 `loginctl show-user trx50 -p Linger` 顯示 `Linger=no`。
- 因此它會在目前登入 session 與之後登入後執行；若要開機但尚未登入也執行，需要手動開：

```bash
sudo loginctl enable-linger trx50
```

看 LM Studio 測試最後一筆：

```bash
latest=$(ls -td logs/lmstudio-crash-test/* | head -1)
echo "$latest"
tail -n 30 "$latest/events.jsonl"
tail -n 30 "$latest/requests.jsonl"
tail -n 30 "$latest/telemetry.csv"
```

重點看：

- crash 前 GPU power 是否突然接近 400W+。
- GPU temp 是否接近 80-90 C。
- VRAM 是否接近滿。
- request 是否開始 timeout 或 500。
- kernel 是否出現 Xid / MCE / thermal。
- log 是否直接斷掉。

## 結論判讀表

| 結果 | 優先嫌疑 |
|---|---|
| kernel 有 OOM | RAM 不足、swap 過小、模型/併發太大 |
| kernel 有 NVIDIA Xid | GPU driver、GPU、PCIe、供電 |
| kernel 有 MCE / hardware error | CPU、RAM、主機板、BIOS |
| MemTest 有錯 | RAM、XMP、插槽、IMC |
| 關 XMP 後穩 | RAM/XMP/IMC |
| GPU PL 350W 穩、450W 不穩 | PSU、12VHPWR、GPU 供電瞬態 |
| CPU baseline 後穩 | BIOS/電壓/CPU power 設定 |
| 沒任何 log，直接斷 | PSU、主機板保護、AC 電源、瞬間過載 |
| LM Studio request error 但系統不重啟 | LM Studio/server/model/API 問題，不是整機硬體斷電 |

## 目前建議的下一步

依目前測試結果，LM Studio 在 `gpt-oss-20b`、concurrency 1/4、GPU 約 300W 以內是穩的。

下一步建議：

1. 用原本會關機的模型、context、併發、prompt 重跑 `lmstudio_crash_test.py` 或手動復現。
2. 若能復現，立刻改 `sudo nvidia-smi -pl 350` 再跑同一組測試。
3. 若 350W 穩，優先查 PSU 型號、ATX 版本、12VHPWR 線材與接法。
4. 若 350W 仍會重啟，關閉 XMP 並重跑。
5. 若關 XMP 仍會重啟，BIOS 載入 Intel default/baseline profile，保留 PL1/PL2 253W，再重跑。
6. 最後做 UEFI MemTest86 過夜，確認 RAM/IMC 不是低頻偶發錯誤。
