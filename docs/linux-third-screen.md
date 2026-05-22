# Linux 三分螢幕使用說明

這份說明用來設定 GNOME Linux 的左/中/右三分螢幕。  
目前這台電腦已設定完成，可以直接使用；搬到其他 Linux 時，照「移植安裝」做即可。

## 目前這台怎麼用

快捷鍵：

- `Ctrl + Alt + 1`：目前視窗移到左邊 1/3
- `Ctrl + Alt + 2`：目前視窗移到中間 1/3
- `Ctrl + Alt + 3`：目前視窗移到右邊 1/3

滑鼠拖曳：

- 拖視窗到螢幕上緣左側後放開：左邊 1/3
- 拖視窗到螢幕上緣中間後放開：中間 1/3
- 拖視窗到螢幕上緣右側後放開：右邊 1/3
- 拖到左邊緣或右邊緣後放開：左/右 1/3

目前相關檔案：

- 快捷鍵核心腳本：`~/.local/bin/third-screen`
- 滑鼠拖曳背景服務腳本：`~/.local/bin/third-screen-drag`
- systemd 使用者服務：`~/.config/systemd/user/third-screen-drag.service`
- Tiling Shell 擴充：`~/.local/share/gnome-shell/extensions/tilingshell@ferrarodomenico.com`

## 適用環境

建議環境：

- GNOME 桌面環境
- X11 / Xorg session
- 有 `python3`、`xrandr`、`libX11`
- 支援 user systemd，也就是可以用 `systemctl --user`

檢查目前是不是 X11：

```bash
echo "$XDG_SESSION_TYPE"
```

如果輸出是：

- `x11`：可以用
- `wayland`：這份腳本不適用，請登出後在登入畫面選 `GNOME on Xorg`

## 移植安裝到其他 Linux

以下用 `~` 表示目前使用者的 home 目錄。

### 1. 建立腳本目錄

```bash
mkdir -p ~/.local/bin ~/.config/systemd/user
```

### 2. 複製腳本

從已設定好的機器複製這兩個檔案到新機器：

```bash
~/.local/bin/third-screen
~/.local/bin/third-screen-drag
```

複製後設定可執行權限：

```bash
chmod +x ~/.local/bin/third-screen ~/.local/bin/third-screen-drag
```

先測試核心腳本：

```bash
~/.local/bin/third-screen center --dry-run
```

如果有印出 `x=... y=... w=... h=...`，代表可以抓到目前視窗和螢幕工作區。

### 3. 設定快捷鍵

GNOME 設定路徑：

`Settings` -> `Keyboard` -> `Keyboard Shortcuts` -> `View and Customize Shortcuts` -> `Custom Shortcuts`

新增三個快捷鍵：

| 名稱 | 指令 | 快捷鍵 |
| --- | --- | --- |
| Third screen: left third | `~/.local/bin/third-screen left` | `Ctrl + Alt + 1` |
| Third screen: center third | `~/.local/bin/third-screen center` | `Ctrl + Alt + 2` |
| Third screen: right third | `~/.local/bin/third-screen right` | `Ctrl + Alt + 3` |

如果 GNOME UI 不接受 `~`，請改成完整路徑，例如：

```bash
/home/你的使用者名稱/.local/bin/third-screen left
```

### 4. 啟用滑鼠拖曳服務

建立服務檔：

`~/.config/systemd/user/third-screen-drag.service`

內容：

```ini
[Unit]
Description=Mouse drag snapping for third-screen
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/third-screen-drag
Restart=always
RestartSec=1

[Install]
WantedBy=default.target
```

啟動服務：

```bash
systemctl --user import-environment DISPLAY XAUTHORITY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP
systemctl --user daemon-reload
systemctl --user enable --now third-screen-drag.service
```

確認服務狀態：

```bash
systemctl --user status third-screen-drag.service --no-pager
```

看到 `active (running)` 就代表已啟動。

## Tiling Shell 拖曳預覽

這台電腦也有使用 GNOME 擴充套件 `Tiling Shell` 來顯示拖曳預覽。

如果其他 Linux 也要有類似預覽：

1. 安裝 GNOME Extension：`Tiling Shell`
2. 設定 layout 為三等分
3. 將 edge tiling mode 設成 `granular`
4. 將 `inner-gaps` 和 `outer-gaps` 設成 `0`

這台目前使用的三等分 layout：

```json
[
  {
    "id": "Thirds",
    "tiles": [
      {"x": 0.0, "y": 0.0, "width": 0.3333333333333333, "height": 1.0, "groups": [1]},
      {"x": 0.3333333333333333, "y": 0.0, "width": 0.3333333333333333, "height": 1.0, "groups": [1, 2]},
      {"x": 0.6666666666666666, "y": 0.0, "width": 0.3333333333333333, "height": 1.0, "groups": [2]}
    ]
  }
]
```

注意：Tiling Shell 更新後，手動修改過的擴充程式碼可能會被覆蓋。純腳本的快捷鍵和拖曳服務不受 Tiling Shell 更新影響。

## 常用管理指令

重啟滑鼠拖曳服務：

```bash
systemctl --user restart third-screen-drag.service
```

查看服務 log：

```bash
journalctl --user -u third-screen-drag.service -n 50 --no-pager
```

暫時停用滑鼠拖曳：

```bash
systemctl --user stop third-screen-drag.service
```

永久停用滑鼠拖曳：

```bash
systemctl --user disable --now third-screen-drag.service
```

移除：

```bash
systemctl --user disable --now third-screen-drag.service
rm -f ~/.config/systemd/user/third-screen-drag.service
rm -f ~/.local/bin/third-screen ~/.local/bin/third-screen-drag
systemctl --user daemon-reload
```

快捷鍵可到 GNOME Keyboard Settings 的 Custom Shortcuts 裡手動刪除。

## 限制

- 這套腳本是 X11 用的，不支援 Wayland。
- 有些應用程式有最小視窗寬度，可能不能縮到完整 1/3。
- 如果其他 tiling 擴充也在接管拖曳，可能會和 `third-screen-drag` 搶控制權。
- 如果看見中間有細縫，通常是 GNOME 視窗陰影或邊框造成；目前 `third-screen` 已用少量重疊像素避開這個問題。
