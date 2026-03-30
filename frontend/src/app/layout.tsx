import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "冰可樂龍蝦 | 台股精銳交易儀表板",
  description: "綜合共振策略 — DMPI × RSI × MACD × AI 強化學習",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body>{children}</body>
    </html>
  );
}
