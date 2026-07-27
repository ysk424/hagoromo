# Changelog

このプロジェクトの主な変更を記録します。

## [0.1.0] - 2026-07-27

### Added

- 羽衣（Hagoromo）として独立した簡易 GPU 布ソルバを初回リリース
- Yohsai 完成服を入力に、アニメーションボディへ追従する CUDA resident solver
- 衣服・拘束・ボディ・BVH・衝突候補・統計を GPU 常駐で保持
- ソルバ反復別に再利用する CUDA Graph 実行経路
- GPU 上のボディ BVH refit、最近傍 Face 探索、Parity Ray 内部判定
- Fast / Standard / Quality / Custom のパフォーマンスプリセット
- 接触クリアランスとソルバ反復の N パネル設定
- 絶対 Shape Key キャッシュと、Driver を Action へ確定するベイク操作
- 日本語 UI（パラメータ・ボタン・状態表示）
- ネイティブ回帰テストと Blender 統合テスト

### Notes

- 過去の Haori CUDA / accelerated 版のビルド履歴は引き継がず、v0.1.0 として新規開始
- Windows x64 のみ
- 布の自己衝突なし
- ボディトポロジーはフレーム範囲内で固定
