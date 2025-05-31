// src/app/layout.js (または該当するレイアウトファイル)
import "./globals.css";

export const metadata = {
  // ★★★ metadataBase を追加 ★★★
  // 本番環境のURLを設定してください。
  // ローカル開発中は http://localhost:3000 のままでも警告は出ますが、
  // 本番デプロイ前に必ず実際のドメインに置き換えてください。
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'),
  title: "PapeLog", // 現在のアプリケーション名
  description: "PDF論文をアップロードするだけ！AIがパッと解析して、論文の構造をまるごとキャッチ...", // 現在の説明文
  openGraph: { // OGP設定の例
    title: "PapeLog",
    description: "PDF論文の解析・管理をスマートに。",
    // images: '/default-og-image.png', // publicフォルダに配置したデフォルトOGP画像
    // 例: images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'PapeLog' }]
  },
  twitter: { // Twitterカード設定の例
    card: 'summary_large_image',
    title: "PapeLog",
    description: "PDF論文の解析・管理をスマートに。",
    // images: ['/twitter-card-image.png'], // publicフォルダに配置したTwitterカード用画像
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="ja">
      <body suppressHydrationWarning={true}>
        {children}
      </body>
    </html>
  );
}