# magpie-flake

[Magpie](https://github.com/yetone/magpie) 的 Nix 打包。

```sh
nix run github:xuanyayi/magpie-flake
```

Magpie 跟踪上游的 [Stable 频道](https://usemagpie.ai/api/latest?channel=stable)。上游常规版本在每周一 00:00 UTC 切换，本仓库在 00:10 UTC 检查，并在通过构建测试后合并更新。

紧急版本进入 Stable 后，可以手动运行 **Update sources**，或由上游集成发送 `magpie-stable-updated` 仓库事件来触发检查。nixpkgs 每日更新时使用已固定的 Magpie 版本。

MIT，改编自 [mtul0729/magpie-flake](https://github.com/mtul0729/magpie-flake)。
