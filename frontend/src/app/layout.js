// frontend/src/app/layout.js
import "./globals.css";

// ★★★ VercelデプロイURLを直接使用するか、環境変数経由で設定 ★★★
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://paper-analyzer-smoky.vercel.app/"; // デプロイURLを設定

export const metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "PapeLog | PDF論文スマート解析・管理",
    template: "%s | PapeLog", 
  },
  description: "PapeLogは、PDF論文をアップロードするだけでAIが構造を解析し、Google Driveに整理・保存。要約やNotion連携で研究効率を劇的に向上させます。",
  
  openGraph: {
    title: "PapeLog | PDF論文の解析・管理を、もっとスマートに。",
    description: "AIがあなたの論文読解と情報整理を強力サポート。Google DriveとNotion連携で知識をストック。",
    url: siteUrl, // ★ アプリケーションのURL
    siteName: "PapeLog",
    images: [
      {
        url: '/og-image.png', // public/og-image.png を配置した場合
        width: 1200,
        height: 630,
        alt: 'PapeLog - PDF論文スマート解析・管理',
      },
    ],
    locale: 'ja_JP',
    type: 'website',
  },

  twitter: {
    card: 'summary_large_image',
    title: "PapeLog: PDF論文の解析・管理をAIで効率化",
    description: "論文の構造解析、Google Drive保存、AI要約、Notion連携。PapeLogで研究をもっとスムーズに。",
    images: ['/twitter-card-image.png'], // public/twitter-card-image.png を配置した場合
  },

  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any', type: 'image/x-icon' }, // app/favicon.ico
      { url: '/icon.png', type: 'image/png', sizes: '32x32' },     // app/icon.png (32x32)
    ],
    apple: [
      { url: '/apple-icon.png', type: 'image/png', sizes: "180x180" }, // app/apple-icon.png (180x180推奨)
    ],
    shortcut: ['/shortcut-icon.png'],
  },
  
  manifest: '/manifest.json', // app/manifest.json
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