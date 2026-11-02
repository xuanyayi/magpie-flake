# magpie-flake

[Magpie](https://github.com/yetone/magpie) 的 Nix 打包。

```sh
nix run github:xuanyayi/magpie-flake
```

插件使用 Nix 提供的 Bun，最低版本为 1.4.4（修复
[CVE-2026-111497](https://github.com/oven-sh/bun/security/advisories/GHSA-663w-cv8g-jj2p)）。
如果 nixpkgs 中的 Bun 版本较旧，本包会使用已合入 nixpkgs 的 1.4.4 官方预编译包；
nixpkgs 提供 1.4.4 或更新版本后自动使用其版本。此策略同样适用于 `follows` 和 overlay。

MIT，改编自 [mtul0729/magpie-flake](https://github.com/mtul0729/magpie-flake)。
