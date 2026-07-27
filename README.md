# 羽衣（Hagoromo）

羽衣は、[Yohsai](https://github.com/ysk424/yohsai) で着付けと縫い合わせを完了した服を、アニメーションするボディへ高速に追従させる Blender Extension です。

個人用の簡易ソルバとして位置付けています。1フレームの物理計算中に服・速度・拘束・ボディ・BVH・衝突候補を GPU メモリへ常駐させます。

- 服の材料構造を四角格子（Quad の Warp/Weft/Shear と軸方向 Bend）として扱う
- ソルバ反復を重ねるほど、隣接頂点と Quad が保存済みの寸法・形状へ収束する
- Yohsai の Seam を閉じ、アニメーションボディとの接触を解く

## 実行モデル

- 衣服の位置・速度・固定状態・Seam・Edge・Quad・Bend をソルバ寿命中 GPU へ常駐
- ボディの BVH トポロジーを作成時に一度構築し、中間姿勢ごとに GPU 上で AABB を Refit
- 最近傍 Face 探索とボディ内外判定を CUDA で実行
- 頂点を共有しない拘束へ Graph Coloring を行い、色単位の CUDA カーネルを CUDA Graph へ記録
- 1フレーム内のボディ中間姿勢では H2D をボディ頂点更新だけに限定し、服の状態は整数フレーム終端まで D2H しない
- 整数フレームで 1 回だけ服の位置・速度・統計を Blender へ戻し、Shape Key キャッシュを作成

## 必要環境

- Blender 5.2 以降（Blender 5.2 LTS で検証）
- Windows x64
- NVIDIA CUDA GPU（Turing 以降。配布 DLL は SM 75/80/86/89/90/100/120 を収録）
- CUDA 12.9 互換の NVIDIA Driver
- Yohsai で Gravity 完了済みの服
- フレーム範囲を通して頂点数と面数が変わらないボディメッシュ

CUDA Runtime と C/C++ Runtime は DLL へ静的リンクするため、配布 ZIP の利用者は CUDA Toolkit や Visual C++ Runtime DLL を別途配置する必要がありません。GPU Driver は必要です。

## インストール

1. `hagoromo-0.1.0-windows-x64.zip` を用意します。
2. Blender の `Edit > Preferences > Extensions` を開きます。
3. メニューから `Install from Disk` を選び、ZIP を指定します。
4. `羽衣` を有効にします。

ZIP を展開する必要はありません。

## 使い方

1. Yohsai で着付け、縫い合わせ、Gravity を完了します。
2. ボディのアーマチュアアニメーションを用意します。
3. 3D Viewport のサイドバーから `羽衣` タブを開きます。
4. `Yohsai 服` と `ボディ` を指定します。
5. `開始フレーム`、`終了フレーム`、パフォーマンスを設定します。
6. `アニメーションをシミュレート` を実行します。
7. 結果を残す場合は `羽衣結果をベイク` を実行します。

実行中は `Esc` でキャンセルできます。元の Yohsai 服は変更せず、結果を `<Yohsai 服名>_HAGOROMO` コレクションへ作成します。

## 速度と品質

| プリセット | ボディステップ | 接触クリアランス | 反復 | 用途 |
| --- | ---: | ---: | ---: | --- |
| 高速 | 2.0 cm | 0.75 cm | 10 | 素早い動きの確認 |
| 標準 | 1.0 cm | 1.0 cm | 20 | 標準プレビュー |
| 高品質 | 0.5 cm | 0.5 cm | 30 | 接触と寸法収束を優先 |
| カスタム | 任意 | 任意 | 任意 | 服とボディに合わせた調整 |

ボディステップを大きくすると中間姿勢が減ります。反復を増やすほど四角格子は保存寸法へ強く戻ります。接触クリアランスを大きくすると貫通への余裕は増えますが、服がボディから浮きます。衝突候補の内部探索距離は 4 cm 固定です。

## 出力とベイク

- 各整数フレームを絶対 Shape Key `HAGOROMO_####` として保存
- Shape Key の `eval_time` をシーンフレームへ追従させる Driver を設定
- 計算範囲、最大ボディ分割数、最大移動量、ソルバ設定、`CUDA_RESIDENT` バックエンドをコレクションへ記録
- 同じ服で再実行すると以前の未ベイク出力を置換
- ベイク済み出力は Driver を通常の Action へ変換し、以後の再計算から保護

## 現在の制限

- CUDA GPU が必須で、CPU fallback はありません
- 布同士の自己衝突は計算しません
- ボディ接触はプレビュー安定性を優先し、ボディの運動量を完全には布へ伝えません
- ボディはフレーム範囲内で同一トポロジーである必要があります
- 整数フレームごとに全頂点を Shape Key へ保存するため、長い範囲では CPU メモリと `.blend` 容量が増えます
- 1フレーム当たりのボディ分割数は最大 512 です

## ソースからのビルド

Visual Studio 2022、CMake 3.24 以降、CUDA Toolkit 12.9 を使用します。

```powershell
.\build_native.ps1 -Configuration Release
```

このスクリプトは DLL をビルドし、ネイティブテストを実行して `bin/hagoromo_cosserat.dll` へインストールします。

Blender 統合テスト:

```powershell
blender --background --factory-startup --python tests\blender_simulation_check.py
```

保存済みファイルの特定コレクションを検証する場合は `HAGOROMO_TEST_CLOTHES` を設定します。

```powershell
$env:HAGOROMO_TEST_CLOTHES = "CLOTHES.001"
blender --background scene.blend --python tests\blender_saved_simulation_check.py
```

詳細は [アーキテクチャ資料](docs/ARCHITECTURE.md) と
[CUDA 開発・検証記録](docs/CUDA_RELEASE_NOTES.md) を参照してください。

## ライセンス

羽衣は GPL-3.0-or-later です。静的リンクした CUDA Runtime については [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照してください。
