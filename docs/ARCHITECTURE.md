# 羽衣 v0.1.0 アーキテクチャ

## 設計目標

羽衣は、Yohsai の完成状態を入力に、四角格子の材料寸法へ反復収束するプレビュー用クロスソルバを GPU 常駐化した個人用簡易ソルバです。頂点単位の厳密一致ではなく、四角形材料、Seam、反復収束、ボディ接触という挙動を維持しながら CPU/GPU 転送と Python 処理を減らすことを目標にします。

## データフロー

```text
Yohsai 保存状態 ──初期化 H2D──> CUDA Solver
  Clothes vertices/velocity       ├─ positions / previous / velocity
  Seam / Edge / Quad / Bend       ├─ constraint colors + CUDA Graph
  Locked vertices                 ├─ Body vertices/faces + GPU BVH
  Body mesh                       └─ collision candidates + stats
                                         │
Blender evaluated Body ─姿勢ごと H2D─────┘
                                         │ GPU 内で全 substep/iteration
                                         ▼
整数フレーム終端 <──位置・速度・統計 D2H── CUDA Solver
        │
        └─ Absolute Shape Key cache
```

服、拘束、ボディ Face、BVH トポロジー、候補 Face、統計はソルバの寿命中 GPU へ常駐します。ボディの頂点位置だけを各中間姿勢で Pinned Host Buffer から非同期転送します。服の状態はボディ step ごとには読み戻さず、整数フレームの出力時だけ同期して D2H します。

## 四角格子と反復収束

Yohsai の材料情報から次の拘束を構築します。

| 拘束 | 保存する Rest 値 | 目的 |
| --- | --- | --- |
| Edge | 隣接頂点の長さ | Warp/Weft 方向の寸法を戻す |
| Quad | `u·u`, `v·v`, `u·v` | 四角形の縦横寸法と Shear を戻す |
| Bend | 同一軸上の前後長 | 軸方向の折れを緩和する |
| Seam | 縫い合わせ頂点ペア | 捕捉後にゼロ長へ閉じる |

拘束は頂点を共有しない集合へ CPU で Greedy Coloring します。同じ色の拘束は互いの書き込み先が重ならないため GPU で並列実行でき、色は順番に処理します。反復ごとに色順を反転し、Edge は 4 sweep 実行します。ソルバ反復を増やすほど保存寸法・Quad metric の誤差が減る設計です。

CUDA は単精度かつ並列であり、補正順序も実装依存です。したがって bitwise reproducibility は保証せず、材料の不変条件と誤差減少をネイティブテストで検証します。

## CUDA Graph

内部 Substep、Seam attraction、積分、拘束色、ボディ contact、速度更新、統計集計からなるカーネル列を、ソルバ反復を Key として CUDA Graph へ Capture します。初回だけ Graph を構築・Instantiate し、以後は 1 回の `cudaGraphLaunch` で同じ計算列を起動します。

単一の長時間 Cooperative Kernel は使いません。通常カーネル境界を全 GPU 同期点として利用するため、GPU 全体を占有する Grid Synchronization に依存せず、大きな格子でも起動できます。

## ボディ BVH と衝突

ボディ Face から平衡二分 BVH のトポロジーを初期化時に CPU で一度作ります。各ボディ姿勢では次を GPU で実行します。

1. Face AABB と内部ノード AABB の refit
2. 各布頂点の最近傍 Face 探索
3. Parity Ray による内外判定
4. 接触候補の生成とクリアランスに基づく押し出し

接触はプレビュー安定性を優先し、ボディの運動量を布へ完全には伝えません。自己衝突はありません。

## Blender 側の役割

- Yohsai 保存状態の読み取りと材料拘束の組み立て
- 依存グラフによるボディ評価とフレーム分割
- 整数フレームでの Shape Key キャッシュ作成
- N パネル（羽衣）からの実行・ベイク操作

ネイティブ DLL 名は `hagoromo_cosserat.dll` です。C API の内部接頭辞 `hsc_` は互換のための実装詳細であり、利用者向けではありません。
