# 羽衣 v0.1.0 CUDA 開発・検証記録

この文書は、会話履歴に依存せず CUDA 実装の設計判断と現在位置を復元するための引継ぎ記録です。

## 位置付け

- リポジトリ: `hagoromo`（羽衣）
- バージョン: `0.1.0`（過去の Haori accelerated ビルドは引き継がない）
- 用途: Yohsai 完成服向けの個人用簡易 GPU 布ソルバ

## 維持する物理的特徴

1. Yohsai の服を Edge、Quad、軸方向 Bend からなる四角格子として扱う。
2. ソルバ反復を増やすほど、隣接長と Quad metric が保存寸法へ近づく。
3. 単精度演算、Graph Coloring、並列実行順による頂点単位の差を許容する。

## Resident 境界

- ソルバ作成時に服、速度、固定状態、Seam、Edge、Quad、Bend、ボディ Face、BVH を GPU へ置く。
- ボディ中間姿勢ごとに転送するのはボディ頂点位置だけ。
- GPU で BVH refit、最近傍 Face 探索、Parity Ray 内部判定、接触候補生成を行う。
- 1フレーム内の複数ボディ step では Cloth state を D2H しない。
- 整数フレーム終端で位置、速度、統計を 1 回だけ D2H し、Blender Shape Key へ保存する。
- ソルバごとの non-blocking CUDA stream 上で転送と CUDA Graph を順序付ける。

## 重要な安定化修正

初期実装では pageable host memory から Legacy Default Stream へ候補 Face をコピーし、その直後に non-blocking Solver Stream の Graph が同じ Buffer を読む競合があった。数十プロセスに 1 回、`illegal memory access` として再現した。

修正後の規則:

- 初期化時の Default Stream upload 完了を、最初の Solver kernel より前に明示する。
- 実行中の H2D は Solver 専用 Stream へ統一する。
- 明示候補用 Host Buffer はソルバの寿命中保持し、非同期転送元を早期解放しない。
- Rollback state とボディ Face 更新は、呼出元 Host Buffer の寿命が切れる前に同期する。
- CUDA Graph は Instantiate 後に `cudaGraphUpload` してから再利用する。
- ソルバ破棄時だけ device boundary を同期して Graph と allocation を安全に解放する。

この規則を崩すと、単発試験では通っても長時間・複数プロセス試験で再発する可能性がある。

## ビルドと検証

```powershell
.\build_native.ps1 -Configuration Release
```

- 成果物: `bin/hagoromo_cosserat.dll`
- ネイティブテスト: `hagoromo_cosserat_tests`
- Blender 統合: `tests/blender_simulation_check.py`

配布 ZIP 利用者は CUDA Toolkit / VC++ Runtime DLL を別途配置する必要はありません。GPU Driver は必要です。
