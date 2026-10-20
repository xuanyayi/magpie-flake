# magpie-flake

[Magpie](https://github.com/yetone/magpie) 的 Nix 打包，支持 x86_64-linux 和 aarch64-linux。

## 使用

```sh
nix build
nix run .
nix flake check
```

## 打包调整

- 关闭使用统计，保留订阅账户发现与切换。
- 主程序和 Bun 由 Nix 管理更新。
- 保留已启用、未固定版本的社区插件自动更新；设置 `MAGPIE_NO_PLUGIN_AUTO_UPDATE=1` 并重启可关闭后台更新及缺失插件补装。插件不受 Nix 锁文件管理。
- 包含桌面启动项和 COSMIC 托盘修复。

## 更新

GitHub Actions 每 6 小时检查最新稳定版，每天 04:00 UTC 更新 nixpkgs；双架构检查通过后提出更新 PR。

```sh
python3 scripts/update.py
python3 scripts/update.py --update-nixpkgs
nix flake check
```

版本与哈希记录在 `sources.json`。

## 许可

MIT。配方及桌面补丁改编自 [mtul0729/magpie-flake](https://github.com/mtul0729/magpie-flake)，保留原许可。
