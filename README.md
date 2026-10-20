# magpie-flake

[Magpie](https://github.com/yetone/magpie) 的 Nix 打包。

```sh
nix run github:xuanyayi/magpie-flake
nix build
nix flake check
```

关闭使用统计；主程序和 Bun 由 Nix 更新，社区插件保留自动更新。

每 6 小时检查 Magpie 稳定版，每天 04:00 UTC 更新 nixpkgs，检查通过后提出 PR。
本地更新：`python3 scripts/update.py --update-nixpkgs`。

MIT，改编自 [mtul0729/magpie-flake](https://github.com/mtul0729/magpie-flake)。
